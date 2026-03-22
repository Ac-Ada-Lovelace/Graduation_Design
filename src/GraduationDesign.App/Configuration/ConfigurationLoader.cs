using System.IO;
using System.Text;
using System.Text.Json;

namespace GraduationDesign.App.Configuration;

public static class ConfigurationLoader
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    public static AppConfiguration LoadOrCreate(string path)
    {
        if (!File.Exists(path))
        {
            var defaultConfiguration = CreateDefaultConfiguration();
            var json = JsonSerializer.Serialize(defaultConfiguration, SerializerOptions);
            File.WriteAllText(path, json, Encoding.UTF8);
            return defaultConfiguration;
        }

        var loadedConfiguration = JsonSerializer.Deserialize<AppConfiguration>(File.ReadAllText(path), SerializerOptions);
        return Normalize(loadedConfiguration ?? new AppConfiguration());
    }

    private static AppConfiguration Normalize(AppConfiguration configuration)
    {
        configuration.Listener ??= new ListenerSettings();
        configuration.Storage ??= new StorageSettings();
        configuration.Devices ??= new Dictionary<int, DeviceSettings>();
        return configuration;
    }

    private static AppConfiguration CreateDefaultConfiguration()
    {
        return new AppConfiguration
        {
            Listener = new ListenerSettings
            {
                Host = "0.0.0.0",
                Port = 5000,
                OfflineTimeoutSeconds = 5
            },
            Storage = new StorageSettings
            {
                Directory = "data",
                FileNamePattern = "measurements-{yyyyMMdd}.jsonl"
            },
            Devices = new Dictionary<int, DeviceSettings>
            {
                [1] = new() { Name = "客厅总表" },
                [2] = new() { Name = "空调回路" },
                [3] = new() { Name = "厨房回路" }
            }
        };
    }
}
