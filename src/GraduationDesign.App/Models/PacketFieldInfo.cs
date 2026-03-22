namespace GraduationDesign.App.Models;

public sealed class PacketFieldInfo
{
    public string Name { get; init; } = string.Empty;

    public string DataType { get; init; } = string.Empty;

    public int Offset { get; init; }

    public int Length { get; init; }

    public string RawHex { get; init; } = string.Empty;

    public string ParsedValue { get; init; } = string.Empty;
}
