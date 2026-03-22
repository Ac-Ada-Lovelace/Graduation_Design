using System.Buffers.Binary;
using System.Globalization;
using GraduationDesign.App.Helpers;
using GraduationDesign.App.Models;

namespace GraduationDesign.App.Services;

public sealed class MeasurementProtocolParser
{
    public const int PacketLength = 44;

    public MeasurementRecord Parse(byte[] packetBytes, string remoteEndPoint, DateTimeOffset receivedAtUtc)
    {
        if (packetBytes.Length != PacketLength)
        {
            return MeasurementRecord.CreatePartialFrame(packetBytes, remoteEndPoint, receivedAtUtc);
        }

        try
        {
            var span = packetBytes.AsSpan();
            var deviceId = BinaryPrimitives.ReadInt32LittleEndian(span.Slice(0, 4));
            var unixTimestamp = BinaryPrimitives.ReadInt32LittleEndian(span.Slice(4, 4));
            var reportTime = DateTimeOffset.FromUnixTimeSeconds(unixTimestamp);
            var currentA = ReadSingle(span.Slice(8, 4));
            var currentB = ReadSingle(span.Slice(12, 4));
            var currentC = ReadSingle(span.Slice(16, 4));
            var voltageA = ReadSingle(span.Slice(20, 4));
            var voltageB = ReadSingle(span.Slice(24, 4));
            var voltageC = ReadSingle(span.Slice(28, 4));
            var powerA = ReadSingle(span.Slice(32, 4));
            var powerB = ReadSingle(span.Slice(36, 4));
            var powerC = ReadSingle(span.Slice(40, 4));

            return new MeasurementRecord
            {
                RawBytes = packetBytes,
                RemoteEndPoint = remoteEndPoint,
                ReceivedAtUtc = receivedAtUtc,
                DeviceId = deviceId,
                ReportTimeUtc = reportTime,
                CurrentA = currentA,
                CurrentB = currentB,
                CurrentC = currentC,
                VoltageA = voltageA,
                VoltageB = voltageB,
                VoltageC = voltageC,
                PowerA = powerA,
                PowerB = powerB,
                PowerC = powerC,
                ParseStatus = PacketParseStatus.Success,
                Fields =
                [
                    CreateField("设备ID", "Int32", 0, span.Slice(0, 4), deviceId.ToString(CultureInfo.InvariantCulture)),
                    CreateField("上报时间", "Int32", 4, span.Slice(4, 4), reportTime.ToString("yyyy-MM-dd HH:mm:ss")),
                    CreateField("电流A", "Float32", 8, span.Slice(8, 4), currentA.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("电流B", "Float32", 12, span.Slice(12, 4), currentB.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("电流C", "Float32", 16, span.Slice(16, 4), currentC.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("电压A", "Float32", 20, span.Slice(20, 4), voltageA.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("电压B", "Float32", 24, span.Slice(24, 4), voltageB.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("电压C", "Float32", 28, span.Slice(28, 4), voltageC.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("功率A", "Float32", 32, span.Slice(32, 4), powerA.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("功率B", "Float32", 36, span.Slice(36, 4), powerB.ToString("0.##", CultureInfo.InvariantCulture)),
                    CreateField("功率C", "Float32", 40, span.Slice(40, 4), powerC.ToString("0.##", CultureInfo.InvariantCulture))
                ]
            };
        }
        catch (Exception exception)
        {
            return new MeasurementRecord
            {
                RawBytes = packetBytes,
                RemoteEndPoint = remoteEndPoint,
                ReceivedAtUtc = receivedAtUtc,
                ParseStatus = PacketParseStatus.ParseError,
                ErrorMessage = exception.Message
            };
        }
    }

    private static float ReadSingle(ReadOnlySpan<byte> bytes)
    {
        var bits = BinaryPrimitives.ReadInt32LittleEndian(bytes);
        return BitConverter.Int32BitsToSingle(bits);
    }

    private static PacketFieldInfo CreateField(string name, string dataType, int offset, ReadOnlySpan<byte> bytes, string value)
    {
        return new PacketFieldInfo
        {
            Name = name,
            DataType = dataType,
            Offset = offset,
            Length = bytes.Length,
            RawHex = HexEncoding.Format(bytes),
            ParsedValue = value
        };
    }
}
