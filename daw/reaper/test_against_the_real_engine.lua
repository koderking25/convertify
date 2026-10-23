-- Runs the script the way Reaper would, against Convertify actually running on this machine.
-- Everything Reaper provides is stood in for; the only thing not really done is the insert
-- itself, which is one documented call. Run with: lua test_against_the_real_engine.lua
--
-- Convertify must be open, and this does convert something, so it does use the network once.

local inserted, said = {}, {}

reaper = {
  ExecProcess = function(cmd, _timeout)
    local pipe = io.popen(cmd .. " 2>/dev/null; echo \"__code:$?\"")
    local all = pipe:read("*a"); pipe:close()
    local body, code = all:match("^(.*)__code:(%d+)%s*$")
    return (code or "0") .. "\n" .. (body or all)
  end,
  GetUserInputs = function(_title, _n, _captions, _defaults)
    return true, (os.getenv("WANTED") or "me at the zoo") .. "," .. (os.getenv("FORMAT") or "wav")
  end,
  ShowMessageBox = function(text, _t, _ty) said[#said + 1] = text; print("  dialog: " .. text) end,
  Help_Set = function(text, _tmp) said[#said + 1] = text; print("  status: " .. text) end,
  Undo_BeginBlock = function() end,
  Undo_EndBlock = function(name, _f) print("  undo point: " .. name) end,
  InsertMedia = function(path, mode) inserted[#inserted + 1] = { path = path, mode = mode } end,
  UpdateArrange = function() end,
  defer = function(fn)
    os.execute("sleep 0.4")
    fn()
  end,
}

dofile("Convertify_Drop_YouTube_Audio_On_A_Track.lua")

print()
if #inserted == 0 then
  print("  FAILED: nothing was put on a track")
  os.exit(1)
end
local one = inserted[1]
print(("  it inserted: %s"):format(one.path))
print(("  with mode %d (1 = new track)"):format(one.mode))
local f = io.open(one.path, "rb")
if not f then print("  FAILED: that file does not exist"); os.exit(1) end
local size = f:seek("end"); f:close()
print(("  the file is really there, %.1f MB"):format(size / 1e6))
if size < 1024 then print("  FAILED: the file is empty"); os.exit(1) end
if one.mode ~= 1 then print("  FAILED: wrong insert mode"); os.exit(1) end
print("\n  PASSED")
