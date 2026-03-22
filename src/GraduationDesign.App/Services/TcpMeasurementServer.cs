using System.Collections.Concurrent;
using System.IO;
using System.Net;
using System.Net.Sockets;
using GraduationDesign.App.Configuration;
using GraduationDesign.App.Models;

namespace GraduationDesign.App.Services;

public sealed class TcpMeasurementServer
{
    private readonly ListenerSettings _settings;
    private readonly MeasurementProtocolParser _parser;
    private readonly ConcurrentDictionary<int, Task> _clientTasks = new();
    private CancellationTokenSource? _cancellationTokenSource;
    private TcpListener? _listener;
    private Task? _acceptLoopTask;
    private int _clientSequence;

    public TcpMeasurementServer(ListenerSettings settings, MeasurementProtocolParser parser)
    {
        _settings = settings;
        _parser = parser;
    }

    public event EventHandler<MeasurementRecord>? RecordReceived;

    public async Task StartAsync()
    {
        if (_listener is not null)
        {
            return;
        }

        _cancellationTokenSource = new CancellationTokenSource();
        _listener = new TcpListener(ParseAddress(_settings.Host), _settings.Port);
        _listener.Start();
        _acceptLoopTask = AcceptLoopAsync(_cancellationTokenSource.Token);
        await Task.CompletedTask;
    }

    public async Task StopAsync()
    {
        if (_cancellationTokenSource is null)
        {
            return;
        }

        _cancellationTokenSource.Cancel();
        _listener?.Stop();

        var tasks = _clientTasks.Values.ToList();
        if (_acceptLoopTask is not null)
        {
            tasks.Add(_acceptLoopTask);
        }

        try
        {
            await Task.WhenAll(tasks);
        }
        catch
        {
        }

        _clientTasks.Clear();
        _listener = null;
        _acceptLoopTask = null;
        _cancellationTokenSource.Dispose();
        _cancellationTokenSource = null;
    }

    private async Task AcceptLoopAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            TcpClient? client = null;

            try
            {
                client = await _listener!.AcceptTcpClientAsync(cancellationToken);
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (ObjectDisposedException)
            {
                break;
            }
            catch (Exception exception)
            {
                PublishRecord(MeasurementRecord.CreateTransportError("-", $"监听异常: {exception.Message}", DateTimeOffset.UtcNow));
            }

            if (client is null)
            {
                continue;
            }

            var clientId = Interlocked.Increment(ref _clientSequence);
            var remoteEndPoint = client.Client.RemoteEndPoint?.ToString() ?? "unknown";
            var clientTask = HandleClientAsync(client, remoteEndPoint, cancellationToken);
            _clientTasks[clientId] = clientTask;

            _ = clientTask.ContinueWith(
                _ => _clientTasks.TryRemove(clientId, out Task? _),
                CancellationToken.None,
                TaskContinuationOptions.None,
                TaskScheduler.Default);
        }
    }

    private async Task HandleClientAsync(TcpClient client, string remoteEndPoint, CancellationToken cancellationToken)
    {
        using var clientRegistration = cancellationToken.Register(() =>
        {
            try
            {
                client.Close();
            }
            catch
            {
            }
        });

        using (client)
        {
            using var stream = client.GetStream();

            while (!cancellationToken.IsCancellationRequested)
            {
                try
                {
                    var frame = await ReadFrameAsync(stream, cancellationToken);

                    if (frame.Length == 0)
                    {
                        break;
                    }

                    if (frame.Length < MeasurementProtocolParser.PacketLength)
                    {
                        PublishRecord(MeasurementRecord.CreatePartialFrame(frame, remoteEndPoint, DateTimeOffset.UtcNow));
                        break;
                    }

                    PublishRecord(_parser.Parse(frame, remoteEndPoint, DateTimeOffset.UtcNow));
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (IOException exception)
                {
                    PublishRecord(MeasurementRecord.CreateTransportError(remoteEndPoint, $"连接中断: {exception.Message}", DateTimeOffset.UtcNow));
                    break;
                }
                catch (SocketException exception)
                {
                    PublishRecord(MeasurementRecord.CreateTransportError(remoteEndPoint, $"Socket 异常: {exception.Message}", DateTimeOffset.UtcNow));
                    break;
                }
                catch (Exception exception)
                {
                    PublishRecord(MeasurementRecord.CreateTransportError(remoteEndPoint, $"连接处理异常: {exception.Message}", DateTimeOffset.UtcNow));
                    break;
                }
            }
        }
    }

    private void PublishRecord(MeasurementRecord record)
    {
        RecordReceived?.Invoke(this, record);
    }

    private static async Task<byte[]> ReadFrameAsync(NetworkStream stream, CancellationToken cancellationToken)
    {
        var buffer = new byte[MeasurementProtocolParser.PacketLength];
        var received = 0;

        while (received < buffer.Length)
        {
            var bytesRead = await stream.ReadAsync(buffer.AsMemory(received, buffer.Length - received), cancellationToken);

            if (bytesRead == 0)
            {
                if (received == 0)
                {
                    return [];
                }

                return buffer[..received];
            }

            received += bytesRead;
        }

        return buffer;
    }

    private static IPAddress ParseAddress(string host)
    {
        if (string.IsNullOrWhiteSpace(host) || host == "0.0.0.0")
        {
            return IPAddress.Any;
        }

        if (IPAddress.TryParse(host, out var parsedAddress))
        {
            return parsedAddress;
        }

        var hostEntry = Dns.GetHostEntry(host);
        return hostEntry.AddressList.First(address => address.AddressFamily == AddressFamily.InterNetwork);
    }
}
