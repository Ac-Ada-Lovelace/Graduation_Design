namespace GraduationDesign.App.Configuration;

public sealed class AppConfiguration
{
    public ListenerSettings Listener { get; set; } = new();

    public StorageSettings Storage { get; set; } = new();

    public Dictionary<int, DeviceSettings> Devices { get; set; } = new();
}

public sealed class ListenerSettings
{
    public string Host { get; set; } = "0.0.0.0";

    public int Port { get; set; } = 5000;

    public int OfflineTimeoutSeconds { get; set; } = 5;
}

public sealed class StorageSettings
{
    public string Directory { get; set; } = "data";

    public string FileNamePattern { get; set; } = "measurements-{yyyyMMdd}.jsonl";
}

public sealed class DeviceSettings
{
    public string Name { get; set; } = string.Empty;
}
