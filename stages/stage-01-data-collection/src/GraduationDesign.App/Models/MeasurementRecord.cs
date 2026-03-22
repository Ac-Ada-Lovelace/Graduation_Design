using GraduationDesign.App.Helpers;

namespace GraduationDesign.App.Models;

public sealed class MeasurementRecord
{
    public Guid Id { get; init; } = Guid.NewGuid();

    public DateTimeOffset ReceivedAtUtc { get; init; } = DateTimeOffset.UtcNow;

    public string RemoteEndPoint { get; init; } = string.Empty;

    public int? DeviceId { get; set; }

    public string DeviceName { get; set; } = string.Empty;

    public DateTimeOffset? ReportTimeUtc { get; init; }

    public float? CurrentA { get; init; }

    public float? CurrentB { get; init; }

    public float? CurrentC { get; init; }

    public float? VoltageA { get; init; }

    public float? VoltageB { get; init; }

    public float? VoltageC { get; init; }

    public float? PowerA { get; init; }

    public float? PowerB { get; init; }

    public float? PowerC { get; init; }

    public PacketParseStatus ParseStatus { get; set; } = PacketParseStatus.Success;

    public string ErrorMessage { get; set; } = string.Empty;

    public byte[] RawBytes { get; init; } = [];

    public IReadOnlyList<PacketFieldInfo> Fields { get; init; } = [];

    public string RawHex => HexEncoding.Format(RawBytes);

    public static MeasurementRecord CreatePartialFrame(byte[] rawBytes, string remoteEndPoint, DateTimeOffset receivedAtUtc)
    {
        return new MeasurementRecord
        {
            RawBytes = rawBytes,
            RemoteEndPoint = remoteEndPoint,
            ReceivedAtUtc = receivedAtUtc,
            ParseStatus = PacketParseStatus.PartialFrame,
            ErrorMessage = $"连接关闭前仅收到 {rawBytes.Length} 字节，未达到 44 字节完整包长度。"
        };
    }

    public static MeasurementRecord CreateTransportError(string remoteEndPoint, string message, DateTimeOffset receivedAtUtc)
    {
        return new MeasurementRecord
        {
            RemoteEndPoint = remoteEndPoint,
            ReceivedAtUtc = receivedAtUtc,
            ParseStatus = PacketParseStatus.TransportError,
            ErrorMessage = message
        };
    }
}
