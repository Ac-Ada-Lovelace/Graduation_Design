using System.Globalization;
using GraduationDesign.App.Models;

namespace GraduationDesign.App.ViewModels;

public sealed class PacketListItemViewModel
{
    public PacketListItemViewModel(MeasurementRecord record)
    {
        Record = record;
    }

    public MeasurementRecord Record { get; }

    public string ReceivedAtText => Record.ReceivedAtUtc.LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss.fff");

    public string DeviceDisplayText => Record.DeviceId is int deviceId
        ? $"{Record.DeviceName} ({deviceId})"
        : "未识别报文";

    public string ReportTimeText => Record.ReportTimeUtc?.LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss") ?? "-";

    public string RemoteEndPoint => string.IsNullOrWhiteSpace(Record.RemoteEndPoint) ? "-" : Record.RemoteEndPoint;

    public string ParseStatusText => Record.ParseStatus switch
    {
        PacketParseStatus.Success => "解析成功",
        PacketParseStatus.PartialFrame => "残缺报文",
        PacketParseStatus.ParseError => "解析失败",
        PacketParseStatus.TransportError => "连接异常",
        PacketParseStatus.StorageError => "存储异常",
        _ => "未知状态"
    };

    public string SummaryText
    {
        get
        {
            if (Record.ParseStatus != PacketParseStatus.Success && !string.IsNullOrWhiteSpace(Record.ErrorMessage))
            {
                return Record.ErrorMessage;
            }

            return $"Ia={FormatNumber(Record.CurrentA)}A, Ua={FormatNumber(Record.VoltageA)}V, Pa={FormatNumber(Record.PowerA)}W";
        }
    }

    private static string FormatNumber(float? value)
    {
        return value?.ToString("0.##", CultureInfo.InvariantCulture) ?? "-";
    }
}
