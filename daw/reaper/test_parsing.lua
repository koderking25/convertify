-- The two functions from the Reaper script that do anything delicate, checked against the
-- shapes Convertify really sends. Run with: lua test_parsing.lua
--
-- The first version of the parser dropped the last character of every value, so "done" read
-- as "don" and the script would have waited for ever on a job that had already finished.
local function field(json, key)
  if not json then return nil end
  -- The closing quote is the first one not preceded by a backslash. The character before it
  -- belongs in the value: an earlier version left it outside the capture and quietly dropped
  -- the last letter of everything, turning "done" into "don".
  local text = json:match('"' .. key .. '"%s*:%s*"(.-[^\\])"')
  if text then return (text:gsub('\\"', '"'):gsub("\\\\", "\\"):gsub("\\/", "/")) end
  if json:match('"' .. key .. '"%s*:%s*""') then return "" end
  local number = json:match('"' .. key .. '"%s*:%s*([%-%d%.]+)')
  if number then return number end
  return json:match('"' .. key .. '"%s*:%s*(%a+)')
end
local function urlencode(s)
  return (s:gsub("[^%w%-%.%_%~]", function(c) return string.format("%%%02X", c:byte()) end))
end

local function slurp(p) local f = io.open(p); local s = f:read("*a"); f:close(); return s end
local pass, fail = 0, 0
local function check(name, got, want)
  if got == want then pass = pass + 1; print(("  PASS  %s = %s"):format(name, tostring(got)))
  else fail = fail + 1; print(("  FAIL  %s = %s, wanted %s"):format(name, tostring(got), tostring(want))) end
end

-- a made up job, shaped exactly like the engine's
local job = '[{"id":"abc123","link":"https://youtu.be/x","quality":"320","kind":"wav",' ..
            '"title":"Chopin - Nocturne (Op. 9 No. 2)","status":"done","stage":"Done",' ..
            '"progress":1.0,"error":null,"file":"Chopin - Nocturne (Op. 9 No. 2).wav",' ..
            '"seconds":278,"limit_seconds":null,"drive_status":null,"slow":false,' ..
            '"folder":"/Users/someone/Downloads"}]'
check("status", field(job, "status"), "done")
check("file name with brackets and spaces", field(job, "file"), "Chopin - Nocturne (Op. 9 No. 2).wav")
check("folder", field(job, "folder"), "/Users/someone/Downloads")
check("id", field(job, "id"), "abc123")

local awkward = '[{"id":"z","title":"He said \\"hi\\" / bye","status":"done",' ..
                '"file":"He said \\"hi\\" - bye.wav","folder":"/x/y"}]'
check("a title with quotes in it", field(awkward, "title"), 'He said "hi" / bye')
check("the file beside it", field(awkward, "file"), 'He said "hi" - bye.wav')

local running = '[{"id":"q","status":"downloading","stage":"Downloading - 1.2 of 4.5 MB - 300 KB/s","file":null,"folder":"/x"}]'
check("a job still going", field(running, "status"), "downloading")
check("its stage line", field(running, "stage"), "Downloading - 1.2 of 4.5 MB - 300 KB/s")

check("url encoding", urlencode("chopin nocturne op 9"), "chopin%20nocturne%20op%209")
check("url encoding of a link", urlencode("https://youtu.be/a_b-c"),
      "https%3A%2F%2Fyoutu.be%2Fa_b-c")

print(("\n  %d passed, %d failed"):format(pass, fail))
os.exit(fail == 0 and 0 or 1)
