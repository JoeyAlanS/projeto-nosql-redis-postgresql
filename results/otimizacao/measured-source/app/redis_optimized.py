"""Índice coberto e agregados diários exatos, sem módulos externos.

As funções Lua são incorporadas ao script de escrita original: validações,
hashes e todos os índices são atualizados na mesma execução standalone.
"""
PREFIX = "iot:opt:v1"
STATE = PREFIX + ":state"
DAY = 86400
SUMMARY_FIELDS = ("count", "sensors", "temperature_sum", "humidity_sum", "alerts", "minimum", "maximum")
BUCKET_FIELDS = ("count", "temperature_sum", "humidity_sum", "alerts", "minimum", "maximum", "first_ts", "last_ts")


def unpack(member):
    from app.store import FIELDS
    return dict(zip(FIELDS, map(int, member.split(",")), strict=True))


WRITE_HELPERS = r"""
local opt_state = redis.call('GET', 'iot:opt:v1:state')
if opt_state == 'building' then return 'BUSY' end
local function opt_change(row, delta)
  if opt_state ~= 'ready' then return end
  local id, sid, ts, t, h = row[1], row[2], tonumber(row[3]), tonumber(row[4]), tonumber(row[5])
  local base = 'iot:opt:v1:sensor:'..sid
  local full = base..':full'
  local day = math.floor(ts/86400)*86400
  local key = base..':day:'..string.format('%.0f',day)
  local member = table.concat(row, ',')
  if delta == 1 then redis.call('ZADD',full,ts,member)
  else redis.call('ZREM',full,member) end
  local count = redis.call('HINCRBY',key,'count',delta)
  if count == 0 then
    redis.call('DEL',key)
    redis.call('ZREM',base..':days',day)
    return
  end
  redis.call('HINCRBY',key,'temperature_sum',delta*t)
  redis.call('HINCRBY',key,'humidity_sum',delta*h)
  redis.call('HINCRBY',key,'alerts',delta*(t > 3200 and 1 or 0))
  local v = redis.call('HMGET',key,'minimum','maximum','first_ts','last_ts')
  if delta == 1 then
    redis.call('HSET',key,'minimum',math.min(tonumber(v[1]) or t,t),
      'maximum',math.max(tonumber(v[2]) or t,t),
      'first_ts',math.min(tonumber(v[3]) or ts,ts),'last_ts',math.max(tonumber(v[4]) or ts,ts))
    redis.call('ZADD',base..':days',day,day)
  elseif t == tonumber(v[1]) or t == tonumber(v[2]) or ts == tonumber(v[3]) or ts == tonumber(v[4]) then
    -- Exclusão de extremo: recalcula somente o dia/sensor afetado.
    local rows = redis.call('ZRANGE',full,day,day+86399,'BYSCORE')
    local low, high, first, last = nil,nil,nil,nil
    for _, packed in ipairs(rows) do
      local _,_,stamp,temp = string.match(packed,'^([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)$')
      stamp,temp = tonumber(stamp),tonumber(temp)
      low = math.min(low or temp,temp); high = math.max(high or temp,temp)
      first = math.min(first or stamp,stamp); last = math.max(last or stamp,stamp)
    end
    redis.call('HSET',key,'minimum',low,'maximum',high,'first_ts',first,'last_ts',last)
  end
end
"""

SUMMARY_LUA = r"""
local first, last = tonumber(ARGV[1]), tonumber(ARGV[2])
local firstday, lastday = math.floor(first/86400)*86400, math.floor(last/86400)*86400
local count,sensors,tsum,hsum,alerts,low,high = 0,0,0,0,0,nil,nil
for _, base in ipairs(KEYS) do
  local before = count
  local days = redis.call('ZRANGE',base..':days',firstday,lastday,'BYSCORE')
  for _, day in ipairs(days) do
    local b = redis.call('HMGET',base..':day:'..day,
      'count','temperature_sum','humidity_sum','alerts','minimum','maximum','first_ts','last_ts')
    if tonumber(b[7]) >= first and tonumber(b[8]) <= last then
      count=count+tonumber(b[1]); tsum=tsum+tonumber(b[2]); hsum=hsum+tonumber(b[3]); alerts=alerts+tonumber(b[4])
      low=math.min(low or tonumber(b[5]),tonumber(b[5])); high=math.max(high or tonumber(b[6]),tonumber(b[6]))
    else
      -- Bordas parciais: lê apenas o intervalo exato, sem arredondar o filtro.
      local rows = redis.call('ZRANGE',base..':full',math.max(first,tonumber(day)),
        math.min(last,tonumber(day)+86399),'BYSCORE')
      for _, packed in ipairs(rows) do
        local _,_,_,t,h = string.match(packed,'^([^,]+),([^,]+),([^,]+),([^,]+),([^,]+)$')
        t,h=tonumber(t),tonumber(h)
        count=count+1; tsum=tsum+t; hsum=hsum+h
        if t > 3200 then alerts=alerts+1 end
        low=math.min(low or t,t); high=math.max(high or t,t)
      end
    end
  end
  if count > before then sensors=sensors+1 end
end
return {count,sensors,tsum,hsum,alerts,low or false,high or false}
"""
