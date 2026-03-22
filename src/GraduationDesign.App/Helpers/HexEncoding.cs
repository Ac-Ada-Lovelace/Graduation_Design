using System.Globalization;
using System.Text;

namespace GraduationDesign.App.Helpers;

public static class HexEncoding
{
    public static string Format(ReadOnlySpan<byte> bytes)
    {
        if (bytes.IsEmpty)
        {
            return string.Empty;
        }

        var builder = new StringBuilder(bytes.Length * 3 - 1);

        for (var index = 0; index < bytes.Length; index++)
        {
            if (index > 0)
            {
                builder.Append(' ');
            }

            builder.Append(bytes[index].ToString("X2", CultureInfo.InvariantCulture));
        }

        return builder.ToString();
    }
}
