using System.Collections.ObjectModel;
using System.Globalization;
using System.Windows;
using System.Windows.Media;
using GraduationDesign.App.Models;

namespace GraduationDesign.App.ViewModels;

public sealed class DeviceViewModel : ObservableObject
{
    private const int MaxRecentPackets = 120;
    private const int MaxEvents = 100;
    private const int MaxTrendPoints = 30;
    private const double SummaryTrendWidth = 160;
    private const double SummaryTrendHeight = 54;
    private const double DetailTrendWidth = 760;
    private const double DetailTrendHeight = 220;

    private string _displayName;
    private bool _isOnline;
    private Brush _statusBrush = Brushes.SlateGray;
    private string _lastReceivedTimeText = "最近接收: -";
    private string _lastReportTimeText = "上报时间: -";
    private string _remoteEndPoint = "-";
    private long _packetCount;
    private string _latestCurrentText = "电流 A/B/C: - / - / -";
    private string _latestVoltageText = "电压 A/B/C: - / - / -";
    private string _latestPowerText = "功率 A/B/C: - / - / -";
    private string _latestPowerAText = "-";
    private string _trendRangeText = "最近 30 点";
    private PointCollection _powerTrendPoints = [];
    private PointCollection _detailPowerTrendPoints = [];
    private readonly Queue<double> _powerASamples = new();

    public DeviceViewModel(int deviceId, string displayName)
    {
        DeviceId = deviceId;
        _displayName = displayName;
    }

    public int DeviceId { get; }

    public string DeviceCodeText => $"设备 ID: {DeviceId}";

    public string DisplayName
    {
        get => _displayName;
        private set => SetProperty(ref _displayName, value);
    }

    public bool IsOnline
    {
        get => _isOnline;
        private set
        {
            if (SetProperty(ref _isOnline, value))
            {
                OnPropertyChanged(nameof(StatusText));
            }
        }
    }

    public string StatusText => IsOnline ? "在线" : "离线";

    public Brush StatusBrush
    {
        get => _statusBrush;
        private set => SetProperty(ref _statusBrush, value);
    }

    public DateTimeOffset? LastReceivedAtUtc { get; private set; }

    public string LastReceivedTimeText
    {
        get => _lastReceivedTimeText;
        private set => SetProperty(ref _lastReceivedTimeText, value);
    }

    public string LastReportTimeText
    {
        get => _lastReportTimeText;
        private set => SetProperty(ref _lastReportTimeText, value);
    }

    public string RemoteEndPoint
    {
        get => _remoteEndPoint;
        private set => SetProperty(ref _remoteEndPoint, value);
    }

    public long PacketCount
    {
        get => _packetCount;
        private set => SetProperty(ref _packetCount, value);
    }

    public string LatestCurrentText
    {
        get => _latestCurrentText;
        private set => SetProperty(ref _latestCurrentText, value);
    }

    public string LatestVoltageText
    {
        get => _latestVoltageText;
        private set => SetProperty(ref _latestVoltageText, value);
    }

    public string LatestPowerText
    {
        get => _latestPowerText;
        private set => SetProperty(ref _latestPowerText, value);
    }

    public string LatestPowerAText
    {
        get => _latestPowerAText;
        private set => SetProperty(ref _latestPowerAText, value);
    }

    public string TrendRangeText
    {
        get => _trendRangeText;
        private set => SetProperty(ref _trendRangeText, value);
    }

    public PointCollection PowerTrendPoints
    {
        get => _powerTrendPoints;
        private set => SetProperty(ref _powerTrendPoints, value);
    }

    public PointCollection DetailPowerTrendPoints
    {
        get => _detailPowerTrendPoints;
        private set => SetProperty(ref _detailPowerTrendPoints, value);
    }

    public ObservableCollection<PacketListItemViewModel> RecentPackets { get; } = new();

    public ObservableCollection<DeviceEventItemViewModel> Events { get; } = new();

    public void ApplyRecord(MeasurementRecord record)
    {
        DisplayName = string.IsNullOrWhiteSpace(record.DeviceName) ? $"设备-{DeviceId}" : record.DeviceName;

        var previousEndPoint = RemoteEndPoint;
        var wasOnline = IsOnline;

        LastReceivedAtUtc = record.ReceivedAtUtc;
        LastReceivedTimeText = $"最近接收: {record.ReceivedAtUtc.LocalDateTime:yyyy-MM-dd HH:mm:ss}";
        LastReportTimeText = $"上报时间: {record.ReportTimeUtc?.LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture) ?? "-"}";
        RemoteEndPoint = string.IsNullOrWhiteSpace(record.RemoteEndPoint) ? "-" : record.RemoteEndPoint;
        PacketCount += 1;

        if (record.ParseStatus == PacketParseStatus.Success)
        {
            LatestCurrentText = $"电流 A/B/C: {FormatMetric(record.CurrentA)} / {FormatMetric(record.CurrentB)} / {FormatMetric(record.CurrentC)}";
            LatestVoltageText = $"电压 A/B/C: {FormatMetric(record.VoltageA)} / {FormatMetric(record.VoltageB)} / {FormatMetric(record.VoltageC)}";
            LatestPowerText = $"功率 A/B/C: {FormatMetric(record.PowerA)} / {FormatMetric(record.PowerB)} / {FormatMetric(record.PowerC)}";
            LatestPowerAText = $"{FormatMetric(record.PowerA)} W";
            AppendPowerSample(record.PowerA);
        }

        RecentPackets.Insert(0, new PacketListItemViewModel(record));
        TrimCollection(RecentPackets, MaxRecentPackets);

        if (!wasOnline)
        {
            SetOnline(true);
            AddEvent("终端上线");
        }
        else if (!string.Equals(previousEndPoint, RemoteEndPoint, StringComparison.OrdinalIgnoreCase))
        {
            AddEvent($"连接地址更新为 {RemoteEndPoint}");
        }

        if (record.ParseStatus != PacketParseStatus.Success)
        {
            AddEvent($"报文异常: {record.ErrorMessage}");
        }
    }

    public bool RefreshStatus(DateTimeOffset now, TimeSpan offlineTimeout)
    {
        if (!IsOnline || LastReceivedAtUtc is null)
        {
            return false;
        }

        if (now - LastReceivedAtUtc.Value <= offlineTimeout)
        {
            return false;
        }

        SetOnline(false);
        AddEvent("终端离线");
        return true;
    }

    private void SetOnline(bool isOnline)
    {
        IsOnline = isOnline;
        StatusBrush = isOnline ? Brushes.SeaGreen : Brushes.SlateGray;
    }

    private void AddEvent(string message)
    {
        Events.Insert(0, new DeviceEventItemViewModel(DateTimeOffset.Now, message));
        TrimCollection(Events, MaxEvents);
    }

    private void AppendPowerSample(float? powerA)
    {
        if (!powerA.HasValue)
        {
            return;
        }

        _powerASamples.Enqueue(powerA.Value);

        while (_powerASamples.Count > MaxTrendPoints)
        {
            _powerASamples.Dequeue();
        }

        RebuildPowerTrend();
    }

    private void RebuildPowerTrend()
    {
        if (_powerASamples.Count == 0)
        {
            PowerTrendPoints = [];
            DetailPowerTrendPoints = [];
            TrendRangeText = "最近 30 点";
            return;
        }

        var values = _powerASamples.ToArray();
        var min = values.Min();
        var max = values.Max();
        var range = max - min;

        if (range < 0.0001)
        {
            range = Math.Max(1.0, Math.Abs(max) * 0.05);
            min -= range / 2;
            max += range / 2;
        }

        PowerTrendPoints = BuildTrendPoints(values, min, max, SummaryTrendWidth, SummaryTrendHeight);
        DetailPowerTrendPoints = BuildTrendPoints(values, min, max, DetailTrendWidth, DetailTrendHeight);
        TrendRangeText = $"{min:0.#}W - {max:0.#}W";
    }

    private static PointCollection BuildTrendPoints(
        IReadOnlyList<double> values,
        double min,
        double max,
        double width,
        double height)
    {
        var points = new PointCollection(values.Count);
        var xStep = values.Count == 1 ? 0 : width / (values.Count - 1);

        for (var index = 0; index < values.Count; index++)
        {
            var normalized = (values[index] - min) / (max - min);
            var x = index * xStep;
            var y = height - (normalized * height);
            points.Add(new Point(x, y));
        }

        if (points.Count == 1)
        {
            points.Add(new Point(width, points[0].Y));
        }

        return points;
    }

    private static string FormatMetric(float? value)
    {
        return value?.ToString("0.##", CultureInfo.InvariantCulture) ?? "-";
    }

    private static void TrimCollection<T>(ObservableCollection<T> collection, int maxCount)
    {
        while (collection.Count > maxCount)
        {
            collection.RemoveAt(collection.Count - 1);
        }
    }
}
