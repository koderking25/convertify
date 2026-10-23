--[[
  Convertify: find something on YouTube and put it on a track.

  @description Convertify - drop YouTube audio onto a track
  @author Convertify
  @version 1.0
  @about
    Asks Convertify for a YouTube video, as a search or a pasted link, waits while it is
    converted, and inserts the result on a new track.

    Convertify must be running. This talks to the engine it already serves on 127.0.0.1:8766,
    the same one its own window uses, so there is nothing extra to install and nothing that can
    drift out of step with the app.

    Reaper has no HTTP of its own, so this shells out to curl, which every Mac has.
]]--

local PORT = 8766
local BASE = "http://127.0.0.1:" .. PORT
local HEADER = '-H "x-convertify: 1"'

local function shell(cmd)
  local out = reaper.ExecProcess(cmd, 0)
  if not out then return nil end
  local newline = out:find("\n")
  if not newline then return nil end
  return out:sub(newline + 1)
end

local function curl(args)
  return shell('/usr/bin/curl -s -m 30 ' .. args)
end

-- Just enough JSON reading for the few fields this needs. What comes back is from Convertify
-- on this machine, and it is still only ever read as data.
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

local function escape(s) return (s:gsub('"', '\\"')) end
local function urlencode(s)
  return (s:gsub("[^%w%-%.%_%~]", function(c) return string.format("%%%02X", c:byte()) end))
end
local function message(text) reaper.ShowMessageBox(text, "Convertify", 0) end
local function tell(text) reaper.Help_Set("Convertify: " .. text, false) end

local function running()
  local status = curl('"' .. BASE .. '/api/status"')
  return status ~= nil and status:find('"version"') ~= nil
end

local function insert(mine)
  local file, folder = field(mine, "file"), field(mine, "folder")
  if not file or not folder then
    message("It finished, but Convertify did not say where it put the file.")
    return
  end
  reaper.Undo_BeginBlock()
  reaper.InsertMedia(folder .. "/" .. file, 1)   -- 1 = add new track, from Reaper's own API
  reaper.Undo_EndBlock("Convertify: " .. file, -1)
  reaper.UpdateArrange()
  tell(file .. " is on a new track")
end

local function main()
  if not running() then
    message("Convertify is not running.\n\nOpen Convertify, then run this again.")
    return
  end

  local ok, answer = reaper.GetUserInputs("Convertify", 2,
    "Song name or YouTube link,Format,extrawidth=280", ",wav")
  if not ok then return end
  local wanted, format = answer:match("^(.-),(.*)$")
  wanted = (wanted or ""):match("^%s*(.-)%s*$")
  format = (format or ""):match("^%s*(.-)%s*$")
  -- WAV by default: a DAW should not have to decode anything, and the import is exact.
  if format == "" then format = "wav" end
  if wanted == "" then return end

  local link = wanted
  if not wanted:find("youtu") then
    tell("looking for " .. wanted)
    local found = curl('"' .. BASE .. '/api/search?q=' .. urlencode(wanted) .. '"')
    local id = found and found:match('"id"%s*:%s*"(.-)"')
    if not id then
      message('Nothing found for "' .. wanted .. '".')
      return
    end
    link = "https://www.youtube.com/watch?v=" .. id
  end

  local body = string.format(
    '{"link":"%s","quality":"320","kind":"%s","limit_seconds":null,"save_to":null,"to_drive":null}',
    escape(link), escape(format))
  local started = curl(HEADER .. ' -H "content-type: application/json" -X POST -d \'' ..
                       body .. '\' "' .. BASE .. '/api/convert"')
  local id = started and field(started, "id")
  if not id then
    message("Convertify would not start that one.\n\n" .. tostring(started))
    return
  end

  -- Wait without freezing Reaper. A loop with a sleep in it blocks the whole program, playback
  -- and mouse included, so this looks once and hands control back each time.
  local looks = 0
  local function look()
    local jobs = curl('"' .. BASE .. '/api/jobs"')
    local mine = (jobs and jobs:match('{[^{}]-"id"%s*:%s*"' .. id .. '".-}')) or jobs
    local state = mine and field(mine, "status") or ""

    if state == "done" then
      insert(mine)
      return
    elseif state == "error" then
      message("Convertify could not do that one.\n\n" .. (field(mine, "error") or ""))
      return
    elseif state == "cancelled" then
      tell("stopped")
      return
    end

    looks = looks + 1
    if looks > 2000 then
      message("Convertify is taking longer than expected. It may still finish on its own, and "
              .. "the file will be in its folder when it does.")
      return
    end
    tell(mine and field(mine, "stage") or "working")
    reaper.defer(look)
  end

  tell("asking for it")
  look()
end

main()
