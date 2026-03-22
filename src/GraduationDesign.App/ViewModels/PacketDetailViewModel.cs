using GraduationDesign.App.Models;

namespace GraduationDesign.App.ViewModels;

public sealed class PacketDetailViewModel
{
    public PacketDetailViewModel(MeasurementRecord record)
    {
        Record = record;
    }

    public MeasurementRecord Record { get; }

    public string WindowTitle => Record.DeviceId is int deviceId
        ? $"协议包详情 - {Record.DeviceName} ({deviceId})"
        : "协议包详情 - 异常报文";

    public string DeviceText => Record.DeviceId is int deviceId
        ? $"{Record.DeviceName} ({deviceId})"
        : "未识别";

    public string ReceivedAtText => Record.ReceivedAtUtc.LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss.fff");

    public string ReportTimeText => Record.ReportTimeUtc?.LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss") ?? "-";

    public string RemoteEndPoint => string.IsNullOrWhiteSpace(Record.RemoteEndPoint) ? "-" : Record.RemoteEndPoint;

    public string ParseStatusText => new PacketListItemViewModel(Record).ParseStatusText;

    public string ErrorMessage => string.IsNullOrWhiteSpace(Record.ErrorMessage) ? "无" : Record.ErrorMessage;

    public string RawHex => string.IsNullOrWhiteSpace(Record.RawHex) ? "(无原始数据)" : Record.RawHex;

    public IReadOnlyList<PacketFieldInfo> Fields => Record.Fields;
}
