-- mpv_bridge.lua — 将 mpv 状态通过 JSON 文件桥接到 Python
-- 每 80ms 把 position/duration/pause/etc 写到 state_file
-- Python 写 cmd_file，mpv 逐行解析执行

local state_file = mp.get_opt("state-file") or ""
local cmd_file = mp.get_opt("cmd-file") or ""
local last_mtime = 0
local last_pos_check = 0

-- 写入状态
local function write_state()
    local pos = mp.get_property_number("time-pos", 0) or 0
    local dur = mp.get_property_number("duration", 0) or 0
    local pause = mp.get_property_bool("pause", true)
    local speed = mp.get_property_number("speed", 1)
    local vol = mp.get_property_number("volume", 70)
    local file = mp.get_property("filename", "")
    local path = mp.get_property("path", "")
    local sub_delay = mp.get_property_number("sub-delay", 0)
    local eof = mp.get_property_bool("eof-reached", false)

    local state = string.format(
        '{"pos":%.3f,"dur":%.3f,"pause":%s,"speed":%.1f,"vol":%d,"file":"%s","path":"%s","sub_delay":%.3f,"eof":%s}',
        pos, dur, pause and "true" or "false", speed, vol,
        file:gsub('"','\\"'):gsub('\n','\\n'),
        path:gsub('"','\\"'):gsub('\n','\\n'),
        sub_delay, eof and "true" or "false"
    )

    if state_file ~= "" then
        local f = io.open(state_file, "w")
        if f then
            f:write(state)
            f:close()
        end
    end
end

-- 定时写状态（80ms 间隔，GUI 更新足够流畅）
mp.add_periodic_timer(0.08, write_state)

-- 定时检查命令文件（500ms，减少磁盘 IO）
local function check_cmds()
    if cmd_file == "" then return end
    local f = io.open(cmd_file, "r")
    if not f then return end
    local content = f:read("*all")
    f:close()

    if not content or content == "" then return end

    -- 清空命令文件
    f = io.open(cmd_file, "w")
    if f then f:close() end

    -- 逐行解析 JSON 命令
    for line in content:gmatch("[^\r\n]+") do
        local ok, cmd = pcall(mp.utils.parse_json, line)
        if ok and cmd and cmd.command then
            if type(cmd.command[1]) == "string" then
                local name = cmd.command[1]
                local args = {}
                for i = 2, #cmd.command do
                    args[i-1] = cmd.command[i]
                end
                local ret = mp.commandv(table.unpack(cmd.command))
            end
        end
    end
end
mp.add_periodic_timer(0.5, check_cmds)

-- 启动时注册
mp.register_event("file-loaded", function()
    write_state()
end)

mp.register_event("end-file", function()
    write_state()
end)

mp.msg.info("bridge.lua loaded — state→" .. state_file .. " cmd←" .. cmd_file)
