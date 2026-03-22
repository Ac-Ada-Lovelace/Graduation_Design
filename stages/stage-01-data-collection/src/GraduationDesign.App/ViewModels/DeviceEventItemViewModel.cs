namespace GraduationDesign.App.ViewModels;

public sealed class DeviceEventItemViewModel
{
    public DeviceEventItemViewModel(DateTimeOffset timestamp, string message)
    {
        Timestamp = timestamp;
        Message = message;
    }

    public DateTimeOffset Timestamp { get; }

    public string TimestampText => Timestamp.LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss");

    public string Message { get; }
}
