using System.Collections.Concurrent;
using System.Collections.ObjectModel;
using System.Windows.Threading;
using GraduationDesign.App.Configuration;
using GraduationDesign.App.Models;
using GraduationDesign.App.Services;

namespace GraduationDesign.App.ViewModels;

public sealed class MainViewModel : ObservableObject
{
    private const int MaxLatestPackets = 200;
    private const int MaxRecentEvents = 60;

    private readonly AppConfiguration _configuration;
    private readonly DeviceCatalog _deviceCatalog;
    private readonly JsonLineMeasurementStorage _storage;
    private readonly TcpMeasurementServer _server;
    private readonly DispatcherTimer _statusTimer;
    private readonly Dictionary<int, DeviceViewModel> _deviceIndex = new();
    private readonly Queue<DateTimeOffset> _recentPacketTimes = new();
    private readonly ConcurrentQueue<MeasurementRecord> _pendingUiRecords = new();
    private readonly TimeSpan _offlineTimeout;

    private string _serverStatusText = "服务未启动";
    private int _onlineDeviceCount;
    private long _totalPacketCount;
    private long _errorPacketCount;
    private int _packetsPerSecond;

    public MainViewModel(
        AppConfiguration configuration,
        DeviceCatalog deviceCatalog,
        JsonLineMeasurementStorage storage,
        TcpMeasurementServer server,
        Dispatcher dispatcher)
    {
        _configuration = configuration;
        _deviceCatalog = deviceCatalog;
        _storage = storage;
        _server = server;
        _offlineTimeout = TimeSpan.FromSeconds(Math.Max(1, configuration.Listener.OfflineTimeoutSeconds));

        Devices = new ObservableCollection<DeviceViewModel>();
        LatestPackets = new ObservableCollection<PacketListItemViewModel>();
        RecentEvents = new ObservableCollection<DeviceEventItemViewModel>();

        _statusTimer = new DispatcherTimer(TimeSpan.FromMilliseconds(500), DispatcherPriority.Background, OnStatusTimerTick, dispatcher);
        _server.RecordReceived += OnRecordReceived;
    }

    public ObservableCollection<DeviceViewModel> Devices { get; }

    public ObservableCollection<PacketListItemViewModel> LatestPackets { get; }

    public ObservableCollection<DeviceEventItemViewModel> RecentEvents { get; }

    public string ServerStatusText
    {
        get => _serverStatusText;
        private set => SetProperty(ref _serverStatusText, value);
    }

    public string ListenerText => $"监听地址: {_configuration.Listener.Host}:{_configuration.Listener.Port}";

    public string StorageText => $"落盘目录: {_storage.StorageDirectoryPath}";

    public int OnlineDeviceCount
    {
        get => _onlineDeviceCount;
        private set => SetProperty(ref _onlineDeviceCount, value);
    }

    public long TotalPacketCount
    {
        get => _totalPacketCount;
        private set => SetProperty(ref _totalPacketCount, value);
    }

    public long ErrorPacketCount
    {
        get => _errorPacketCount;
        private set => SetProperty(ref _errorPacketCount, value);
    }

    public int PacketsPerSecond
    {
        get => _packetsPerSecond;
        private set
        {
            if (SetProperty(ref _packetsPerSecond, value))
            {
                OnPropertyChanged(nameof(PacketsPerSecondText));
            }
        }
    }

    public string PacketsPerSecondText => $"{PacketsPerSecond} pkt/s";

    public async Task StartAsync()
    {
        ServerStatusText = "服务启动中...";
        await _server.StartAsync();
        ServerStatusText = "服务运行中";
        _statusTimer.Start();
    }

    public async Task StopAsync()
    {
        _statusTimer.Stop();
        await _server.StopAsync();
        ServerStatusText = "服务已停止";
    }

    private void OnRecordReceived(object? sender, MeasurementRecord record)
    {
        _ = HandleRecordAsync(record);
    }

    private async Task HandleRecordAsync(MeasurementRecord record)
    {
        if (record.DeviceId is int deviceId)
        {
            record.DeviceName = _deviceCatalog.ResolveName(deviceId);
        }

        try
        {
            await _storage.AppendAsync(record);
        }
        catch (Exception exception)
        {
            record.ParseStatus = PacketParseStatus.StorageError;
            record.ErrorMessage = string.IsNullOrWhiteSpace(record.ErrorMessage)
                ? $"写入文件失败: {exception.Message}"
                : $"{record.ErrorMessage} | 写入文件失败: {exception.Message}";
        }

        _pendingUiRecords.Enqueue(record);
    }

    private void ApplyRecord(MeasurementRecord record)
    {
        TotalPacketCount += 1;

        if (record.ParseStatus != PacketParseStatus.Success)
        {
            ErrorPacketCount += 1;
        }

        LatestPackets.Insert(0, new PacketListItemViewModel(record));
        TrimCollection(LatestPackets, MaxLatestPackets);

        if (record.DeviceId is int deviceId)
        {
            var device = GetOrCreateDevice(deviceId, record.DeviceName, out var created);
            var wasOnline = device.IsOnline;
            device.ApplyRecord(record);

            if (created)
            {
                AddRecentEvent($"发现终端 {device.DisplayName} ({deviceId})");
            }

            if (!wasOnline && device.IsOnline)
            {
                AddRecentEvent($"{device.DisplayName} ({deviceId}) 已上线");
            }
        }

        _recentPacketTimes.Enqueue(record.ReceivedAtUtc);
        RefreshPacketRate(record.ReceivedAtUtc);
        RefreshOnlineDeviceCount();

        if (record.ParseStatus != PacketParseStatus.Success)
        {
            AddRecentEvent(BuildPacketErrorMessage(record));
        }
    }

    private DeviceViewModel GetOrCreateDevice(int deviceId, string deviceName, out bool created)
    {
        if (_deviceIndex.TryGetValue(deviceId, out var existing))
        {
            created = false;
            return existing;
        }

        var resolvedName = string.IsNullOrWhiteSpace(deviceName) ? _deviceCatalog.ResolveName(deviceId) : deviceName;
        var createdDevice = new DeviceViewModel(deviceId, resolvedName);
        _deviceIndex[deviceId] = createdDevice;
        Devices.Insert(0, createdDevice);
        created = true;
        return createdDevice;
    }

    private void OnStatusTimerTick(object? sender, EventArgs e)
    {
        var now = DateTimeOffset.UtcNow;
        var anyStatusChanged = false;
        var flushedAnyRecord = DrainPendingRecords();

        foreach (var device in Devices)
        {
            if (device.RefreshStatus(now, _offlineTimeout))
            {
                anyStatusChanged = true;
                AddRecentEvent($"{device.DisplayName} ({device.DeviceId}) 已离线");
            }
        }

        RefreshPacketRate(now);

        if (anyStatusChanged || flushedAnyRecord)
        {
            RefreshOnlineDeviceCount();
        }
    }

    private bool DrainPendingRecords()
    {
        var drainedAny = false;
        var processed = 0;

        while (processed < 500 && _pendingUiRecords.TryDequeue(out var record))
        {
            ApplyRecord(record);
            drainedAny = true;
            processed += 1;
        }

        return drainedAny;
    }

    private void RefreshPacketRate(DateTimeOffset now)
    {
        while (_recentPacketTimes.Count > 0 && now - _recentPacketTimes.Peek() > TimeSpan.FromSeconds(1))
        {
            _recentPacketTimes.Dequeue();
        }

        PacketsPerSecond = _recentPacketTimes.Count;
    }

    private void RefreshOnlineDeviceCount()
    {
        OnlineDeviceCount = Devices.Count(device => device.IsOnline);
    }

    private void AddRecentEvent(string message)
    {
        RecentEvents.Insert(0, new DeviceEventItemViewModel(DateTimeOffset.Now, message));
        TrimCollection(RecentEvents, MaxRecentEvents);
    }

    private static string BuildPacketErrorMessage(MeasurementRecord record)
    {
        var source = record.DeviceId is int deviceId
            ? $"{record.DeviceName} ({deviceId})"
            : "未识别终端";

        return string.IsNullOrWhiteSpace(record.ErrorMessage)
            ? $"{source} 发生异常报文"
            : $"{source} 异常: {record.ErrorMessage}";
    }

    private static void TrimCollection<T>(ObservableCollection<T> collection, int maxCount)
    {
        while (collection.Count > maxCount)
        {
            collection.RemoveAt(collection.Count - 1);
        }
    }
}
