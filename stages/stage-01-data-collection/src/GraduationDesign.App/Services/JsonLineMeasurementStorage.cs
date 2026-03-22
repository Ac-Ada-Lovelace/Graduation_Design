using System.IO;
using System.Text;
using System.Text.Json;
using GraduationDesign.App.Configuration;
using GraduationDesign.App.Models;

namespace GraduationDesign.App.Services;

public sealed class JsonLineMeasurementStorage
{
    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        WriteIndented = false
    };

    private readonly StorageSettings _settings;
    private readonly SemaphoreSlim _writeGate = new(1, 1);

    public JsonLineMeasurementStorage(StorageSettings settings, string baseDirectory)
    {
        _settings = settings;
        StorageDirectoryPath = Path.GetFullPath(Path.Combine(baseDirectory, settings.Directory));
    }

    public string StorageDirectoryPath { get; }

    public async Task AppendAsync(MeasurementRecord record, CancellationToken cancellationToken = default)
    {
        Directory.CreateDirectory(StorageDirectoryPath);

        var filePath = Path.Combine(StorageDirectoryPath, ResolveFileName(record.ReceivedAtUtc));
        var storageRecord = new
        {
            receivedAt = record.ReceivedAtUtc.UtcDateTime,
            remoteEndPoint = record.RemoteEndPoint,
            deviceId = record.DeviceId,
            deviceName = record.DeviceName,
            reportTimeUtc = record.ReportTimeUtc?.UtcDateTime,
            currentA = record.CurrentA,
            currentB = record.CurrentB,
            currentC = record.CurrentC,
            voltageA = record.VoltageA,
            voltageB = record.VoltageB,
            voltageC = record.VoltageC,
            powerA = record.PowerA,
            powerB = record.PowerB,
            powerC = record.PowerC,
            parseStatus = record.ParseStatus.ToString(),
            errorMessage = record.ErrorMessage,
            rawHex = record.RawHex
        };

        var line = JsonSerializer.Serialize(storageRecord, SerializerOptions) + Environment.NewLine;

        await _writeGate.WaitAsync(cancellationToken);

        try
        {
            await File.AppendAllTextAsync(filePath, line, Encoding.UTF8, cancellationToken);
        }
        finally
        {
            _writeGate.Release();
        }
    }

    private string ResolveFileName(DateTimeOffset timestamp)
    {
        return _settings.FileNamePattern.Replace("{yyyyMMdd}", timestamp.ToString("yyyyMMdd"));
    }
}
