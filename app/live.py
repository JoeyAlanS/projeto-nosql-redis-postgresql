"""Estado operacional: leituras diretas e manutenção incremental de dois escopos."""
from contextlib import contextmanager
from app.store import pg_connect, redis_connect, Busy, Invalid, ROOT

PREFIX='iot:live:v1'
STATE=PREFIX+':status'
FIELDS=('sensor_id','ts','temperature_centi','humidity_centi','location')
METRICS=('count','temperature_sum','humidity_sum','alerts','minimum','maximum')
EMPTY=dict(count=0,temperature_sum=0,humidity_sum=0,alerts=0,minimum=None,maximum=None)


def scope(location=None):
    return 'all' if location is None else 'location:'+location


def numeric(row):
    return {k:(v if k=='location' else int(v)) for k,v in row.items()} if row else None


WRITE_LUA=r'''
if redis.call('GET','iot:live:v1:status') ~= 'ready' then return 'BUSY' end
local sid,ts,t,h,remove=ARGV[1],ARGV[2],tonumber(ARGV[3]),tonumber(ARGV[4]),ARGV[5]
local location=redis.call('HGET','iot:sensor:'..sid,'location')
if not location then return 'INVALID' end
local key='iot:live:v1:sensor:'..sid
local old=redis.call('HMGET',key,'ts','temperature_centi','humidity_centi','location')
if old[1] and old[4] ~= location then return 'INVALID' end
local oldcount=old[1] and 1 or 0
local newcount=remove=='1' and 0 or 1
local ot,oh=tonumber(old[2]) or 0,tonumber(old[3]) or 0
if newcount==0 then redis.call('DEL',key)
else redis.call('HSET',key,'sensor_id',sid,'ts',ts,'temperature_centi',ARGV[3],'humidity_centi',ARGV[4],'location',location) end
local member=string.format('%010d',tonumber(sid))
local function adjust(group)
  local base='iot:live:v1:group:'..group
  local stats=base..':summary'
  local ordered=base..':temperatures'
  if newcount==0 then redis.call('ZREM',ordered,member)
  else redis.call('ZADD',ordered,t,member) end
  local count=redis.call('HINCRBY',stats,'count',newcount-oldcount)
  redis.call('HINCRBY',stats,'temperature_sum',newcount*t-oldcount*ot)
  redis.call('HINCRBY',stats,'humidity_sum',newcount*h-oldcount*oh)
  redis.call('HINCRBY',stats,'alerts',newcount*(t>3200 and 1 or 0)-oldcount*(ot>3200 and 1 or 0))
  if count==0 then redis.call('HDEL',stats,'minimum','maximum')
  else
    local low=redis.call('ZRANGE',ordered,0,0,'WITHSCORES')
    local high=redis.call('ZRANGE',ordered,0,0,'REV','WITHSCORES')
    redis.call('HSET',stats,'minimum',low[2],'maximum',high[2])
  end
end
adjust('all')
adjust('location:'..location)
return 'OK'
'''


class RedisLive:
    def __init__(self, connection):
        self.conn=connection
        if connection.get(STATE)!='ready': raise Busy('Execute make preparar-central')
        self._write=connection.register_script(WRITE_LUA)

    def latest(self,sensor_id):
        return numeric(self.conn.hgetall(f'{PREFIX}:sensor:{sensor_id}'))

    def summary(self,location=None):
        values=self.conn.hgetall(f'{PREFIX}:group:{scope(location)}:summary')
        return {**EMPTY,**{k:int(v) for k,v in values.items()}}

    def alerts(self,location=None,limit=20):
        rows=self.conn.zrevrangebyscore(f'{PREFIX}:group:{scope(location)}:temperatures',
                                      '+inf','(3200',start=0,num=limit,withscores=True)
        return [dict(sensor_id=int(sid),temperature_centi=int(t)) for sid,t in rows]

    def write(self,sensor_id,ts=1,temperature_centi=0,humidity_centi=0,remove=False):
        validate(sensor_id,ts,temperature_centi,humidity_centi)
        result=self._write(args=[sensor_id,ts,temperature_centi,humidity_centi,int(remove)])
        if result=='BUSY': raise Busy('Central indisponível durante preparação')
        if result=='INVALID': raise Invalid('Sensor inexistente ou cadastro de local alterado')
        return {'sensor_id':sensor_id,'removed':remove}


def validate(sid,ts,t,h):
    from app.store import MAX_SENSOR_ID,MAX_TIMESTAMP
    for value,lo,hi in ((sid,1,MAX_SENSOR_ID),(ts,1,MAX_TIMESTAMP),(t,-5000,10000),(h,0,10000)):
        if type(value) is not int or not lo<=value<=hi: raise Invalid('Estado fora dos limites permitidos')


class PostgresLive:
    def __init__(self,connection):
        self.conn=connection
        try:
            row=connection.execute("SELECT ready FROM live_metadata WHERE singleton=true").fetchone()
        except Exception as exc:
            raise Busy('Execute make preparar-central') from exc
        if not row or not row['ready']: raise Busy('Execute make preparar-central')

    def latest(self,sensor_id):
        return self.conn.execute('SELECT sensor_id,ts,temperature_centi,humidity_centi,location FROM live_states WHERE sensor_id=%s',(sensor_id,)).fetchone()

    def summary(self,location=None):
        return self.conn.execute('SELECT count,temperature_sum,humidity_sum,alerts,minimum,maximum FROM live_summaries WHERE scope=%s',(scope(location),)).fetchone() or dict(EMPTY)

    def alerts(self,location=None,limit=20):
        if location is None:
            return self.conn.execute('SELECT sensor_id,temperature_centi FROM live_states WHERE temperature_centi>3200 ORDER BY temperature_centi DESC,sensor_id DESC LIMIT %s',(limit,)).fetchall()
        return self.conn.execute('SELECT sensor_id,temperature_centi FROM live_states WHERE location=%s AND temperature_centi>3200 ORDER BY temperature_centi DESC,sensor_id DESC LIMIT %s',(location,limit)).fetchall()

    def write(self,sensor_id,ts=1,temperature_centi=0,humidity_centi=0,remove=False):
        validate(sensor_id,ts,temperature_centi,humidity_centi)
        result=self.conn.execute('SELECT live_write(%s,%s,%s,%s,%s) AS result',(sensor_id,ts,temperature_centi,humidity_centi,remove)).fetchone()['result']
        if result=='BUSY':raise Busy('Central indisponível durante preparação')
        if result=='INVALID':raise Invalid('Sensor inexistente ou cadastro de local alterado')
        return {'sensor_id':sensor_id,'removed':remove}


@contextmanager
def live_store(source):
    if source=='redis':
        with redis_connect() as c:yield RedisLive(c)
    elif source=='postgres':
        with pg_connect() as c:yield PostgresLive(c)
    else:raise Invalid('Fonte inválida')
