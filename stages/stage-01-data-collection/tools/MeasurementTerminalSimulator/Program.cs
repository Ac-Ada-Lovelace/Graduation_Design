using System.Buffers.Binary;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

var jsonOptions = new JsonSerializerOptions
{
    PropertyNameCaseInsensitive = true,
    WriteIndented = true
};

var baseDirectory = ResolveBaseDirectory();
var simulatorSettingsPath = Path.Combine(baseDirectory, "tools", "MeasurementTerminalSimulator", "simulator.settings.json");
var simulatorSettings = LoadOrCreateSimulatorSettings(simulatorSettingsPath, jsonOptions);
var appConfigPath = ResolveAppConfigPath(baseDirectory, simulatorSettings.AppConfigPath);
var appConfig = LoadAppConfiguration(appConfigPath, jsonOptions);

var host = ResolveHost(simulatorSettings.ConnectHost, appConfig.Listener.Host);
var port = simulatorSettings.ConnectPort > 0 ? simulatorSettings.ConnectPort : appConfig.Listener.Port;
var deviceIds = ResolveDeviceIds(
    simulatorSettings.EnabledDeviceIds,
    simulatorSettings.EnabledDeviceIdRanges,
    appConfig.Devices);

if (deviceIds.Count == 0)
{
    Console.WriteLine("未找到可模拟的设备 ID。请先在 src/GraduationDesign.App/appsettings.json 的 Devices 节点中配置设备。");
    return 1;
}

Console.OutputEncoding = Encoding.UTF8;
Console.WriteLine("Measurement Terminal Simulator");
Console.WriteLine($"目标地址: {host}:{port}");
Console.WriteLine($"配置文件: {appConfigPath}");
Console.WriteLine($"模拟终端: {string.Join(", ", deviceIds.Select(id => $"{id}-{ResolveDeviceName(id, appConfig.Devices)}"))}");
Console.WriteLine("按 Ctrl+C 停止。");
Console.WriteLine();

using var cancellation = new CancellationTokenSource();
Console.CancelKeyPress += (_, eventArgs) =>
{
    eventArgs.Cancel = true;
    cancellation.Cancel();
};

var tasks = deviceIds
    .Select(deviceId => RunTerminalAsync(
        deviceId,
        ResolveDeviceName(deviceId, appConfig.Devices),
        host,
        port,
        TimeSpan.FromMilliseconds(Math.Max(200, simulatorSettings.SendIntervalMilliseconds)),
        TimeSpan.FromMilliseconds(Math.Max(500, simulatorSettings.ReconnectDelayMilliseconds)),
        cancellation.Token))
    .ToArray();

try
{
    await Task.WhenAll(tasks);
}
catch (OperationCanceledException)
{
}

return 0;

static async Task RunTerminalAsync(
    int deviceId,
    string deviceName,
    string host,
    int port,
    TimeSpan sendInterval,
    TimeSpan reconnectDelay,
    CancellationToken cancellationToken)
{
    var state = new DeviceSignalState(deviceId);

    while (!cancellationToken.IsCancellationRequested)
    {
        try
        {
            using var client = new TcpClient();
            await client.ConnectAsync(host, port, cancellationToken);
            using var stream = client.GetStream();

            WriteLine(deviceId, $"已连接 {host}:{port} ({deviceName})");

            while (!cancellationToken.IsCancellationRequested)
            {
                var packet = BuildPacket(deviceId, state);
                await stream.WriteAsync(packet, cancellationToken);
                await stream.FlushAsync(cancellationToken);
                state.IncrementSendCount();

                if (state.ShouldReport())
                {
                    WriteLine(deviceId, $"持续发送中，累计 {state.SendCount} 包");
                }

                await Task.Delay(sendInterval, cancellationToken);
            }
        }
        catch (OperationCanceledException)
        {
            break;
        }
        catch (Exception exception)
        {
            WriteLine(deviceId, $"连接失败或中断: {exception.Message}");
            await Task.Delay(reconnectDelay, cancellationToken);
        }
    }
}

static byte[] BuildPacket(int deviceId, DeviceSignalState _)
{
    var now = DateTimeOffset.UtcNow;
    var seconds = now.ToUnixTimeMilliseconds() / 1000.0;
    var phase = seconds + (deviceId * 0.7);

    var currentA = (float)(4.5 + (deviceId * 0.75) + Math.Sin(phase) * 0.9);
    var currentB = (float)(2.2 + (deviceId * 0.45) + Math.Sin(phase * 0.8 + 1.1) * 0.6);
    var currentC = (float)(1.4 + (deviceId * 0.35) + Math.Sin(phase * 1.2 + 2.1) * 0.4);

    var voltageA = (float)(220.0 + Math.Sin(phase * 0.5) * 3.0);
    var voltageB = (float)(221.0 + Math.Sin(phase * 0.55 + 0.4) * 2.4);
    var voltageC = (float)(219.5 + Math.Sin(phase * 0.52 + 0.9) * 2.7);

    var powerA = (float)(currentA * voltageA * 0.91);
    var powerB = (float)(currentB * voltageB * 0.88);
    var powerC = (float)(currentC * voltageC * 0.85);

    var buffer = new byte[44];
    BinaryPrimitives.WriteInt32LittleEndian(buffer.AsSpan(0, 4), deviceId);
    BinaryPrimitives.WriteInt32LittleEndian(buffer.AsSpan(4, 4), (int)now.ToUnixTimeSeconds());
    WriteSingle(buffer.AsSpan(8, 4), currentA);
    WriteSingle(buffer.AsSpan(12, 4), currentB);
    WriteSingle(buffer.AsSpan(16, 4), currentC);
    WriteSingle(buffer.AsSpan(20, 4), voltageA);
    WriteSingle(buffer.AsSpan(24, 4), voltageB);
    WriteSingle(buffer.AsSpan(28, 4), voltageC);
    WriteSingle(buffer.AsSpan(32, 4), powerA);
    WriteSingle(buffer.AsSpan(36, 4), powerB);
    WriteSingle(buffer.AsSpan(40, 4), powerC);

    return buffer;
}

static void WriteSingle(Span<byte> destination, float value)
{
    BinaryPrimitives.WriteInt32LittleEndian(destination, BitConverter.SingleToInt32Bits(value));
}

static string ResolveBaseDirectory()
{
    var current = new DirectoryInfo(AppContext.BaseDirectory);

    while (current is not null)
    {
        if (File.Exists(Path.Combine(current.FullName, "build-and-run-windows.bat")))
        {
            return current.FullName;
        }

        current = current.Parent;
    }

    return Directory.GetCurrentDirectory();
}

static SimulatorSettings LoadOrCreateSimulatorSettings(string path, JsonSerializerOptions jsonOptions)
{
    if (!File.Exists(path))
    {
        var defaults = new SimulatorSettings();
        var json = JsonSerializer.Serialize(defaults, jsonOptions);
        File.WriteAllText(path, json, Encoding.UTF8);
        return defaults;
    }

    var loaded = JsonSerializer.Deserialize<SimulatorSettings>(File.ReadAllText(path), jsonOptions);
    return loaded ?? new SimulatorSettings();
}

static AppConfiguration LoadAppConfiguration(string path, JsonSerializerOptions jsonOptions)
{
    if (!File.Exists(path))
    {
        throw new FileNotFoundException($"未找到后台配置文件: {path}");
    }

    var loaded = JsonSerializer.Deserialize<AppConfiguration>(File.ReadAllText(path), jsonOptions);
    if (loaded is null)
    {
        throw new InvalidOperationException("后台配置文件解析失败。");
    }

    loaded.Listener ??= new ListenerSettings();
    loaded.Devices ??= new Dictionary<int, DeviceSettings>();
    return loaded;
}

static string ResolveAppConfigPath(string baseDirectory, string configuredPath)
{
    if (Path.IsPathRooted(configuredPath))
    {
        return configuredPath;
    }

    return Path.GetFullPath(Path.Combine(baseDirectory, configuredPath));
}

static string ResolveHost(string? overrideHost, string configuredHost)
{
    var host = string.IsNullOrWhiteSpace(overrideHost) ? configuredHost : overrideHost.Trim();
    return host switch
    {
        "" => "127.0.0.1",
        "0.0.0.0" => "127.0.0.1",
        "::" => "127.0.0.1",
        _ => host
    };
}

static List<int> ResolveDeviceIds(
    IReadOnlyList<int>? configuredIds,
    IReadOnlyList<string>? configuredRanges,
    IReadOnlyDictionary<int, DeviceSettings> devices)
{
    var resolved = new HashSet<int>();

    if (configuredIds is { Count: > 0 })
    {
        foreach (var configuredId in configuredIds)
        {
            resolved.Add(configuredId);
        }
    }

    if (configuredRanges is { Count: > 0 })
    {
        foreach (var range in configuredRanges)
        {
            foreach (var value in ParseRange(range))
            {
                resolved.Add(value);
            }
        }
    }

    if (resolved.Count > 0)
    {
        return resolved.OrderBy(id => id).ToList();
    }

    return devices.Keys.OrderBy(id => id).ToList();
}

static string ResolveDeviceName(int deviceId, IReadOnlyDictionary<int, DeviceSettings> devices)
{
    if (devices.TryGetValue(deviceId, out var settings) && !string.IsNullOrWhiteSpace(settings.Name))
    {
        return settings.Name;
    }

    return $"设备-{deviceId}";
}

static void WriteLine(int deviceId, string message)
{
    Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] [终端 {deviceId}] {message}");
}

static IEnumerable<int> ParseRange(string? rangeExpression)
{
    if (string.IsNullOrWhiteSpace(rangeExpression))
    {
        yield break;
    }

    var trimmed = rangeExpression.Trim();
    if (!trimmed.Contains('-'))
    {
        if (int.TryParse(trimmed, out var single))
        {
            yield return single;
        }

        yield break;
    }

    var parts = trimmed.Split('-', 2, StringSplitOptions.TrimEntries);
    if (parts.Length != 2
        || !int.TryParse(parts[0], out var start)
        || !int.TryParse(parts[1], out var end))
    {
        yield break;
    }

    if (end < start)
    {
        (start, end) = (end, start);
    }

    for (var value = start; value <= end; value++)
    {
        yield return value;
    }
}

internal sealed class DeviceSignalState
{
    private int _sendsSinceLastReport;

    public DeviceSignalState(int deviceId)
    {
        DeviceId = deviceId;
    }

    public int DeviceId { get; }

    public long SendCount { get; private set; }

    public void IncrementSendCount()
    {
        SendCount += 1;
        _sendsSinceLastReport += 1;
    }

    public bool ShouldReport()
    {
        if (_sendsSinceLastReport < 10)
        {
            return false;
        }

        _sendsSinceLastReport = 0;
        return true;
    }
}

internal sealed class SimulatorSettings
{
    public string AppConfigPath { get; set; } = "src/GraduationDesign.App/appsettings.json";

    public string ConnectHost { get; set; } = string.Empty;

    public int ConnectPort { get; set; }

    public List<int> EnabledDeviceIds { get; set; } = [];

    public List<string> EnabledDeviceIdRanges { get; set; } = [];

    public int SendIntervalMilliseconds { get; set; } = 1000;

    public int ReconnectDelayMilliseconds { get; set; } = 1500;
}

internal sealed class AppConfiguration
{
    public ListenerSettings Listener { get; set; } = new();

    public Dictionary<int, DeviceSettings> Devices { get; set; } = new();
}

internal sealed class ListenerSettings
{
    public string Host { get; set; } = "0.0.0.0";

    public int Port { get; set; } = 5000;
}

internal sealed class DeviceSettings
{
    public string Name { get; set; } = string.Empty;
}
