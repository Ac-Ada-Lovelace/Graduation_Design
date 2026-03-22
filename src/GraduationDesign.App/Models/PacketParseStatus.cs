namespace GraduationDesign.App.Models;

public enum PacketParseStatus
{
    Success,
    PartialFrame,
    ParseError,
    TransportError,
    StorageError
}
