using GraduationDesign.App.Configuration;

namespace GraduationDesign.App.Services;

public sealed class DeviceCatalog
{
    private readonly IReadOnlyDictionary<int, DeviceSettings> _devices;

    public DeviceCatalog(IReadOnlyDictionary<int, DeviceSettings> devices)
    {
        _devices = devices;
    }

    public string ResolveName(int deviceId)
    {
        if (_devices.TryGetValue(deviceId, out var deviceSettings) && !string.IsNullOrWhiteSpace(deviceSettings.Name))
        {
            return deviceSettings.Name;
        }

        return $"设备-{deviceId}";
    }
}
