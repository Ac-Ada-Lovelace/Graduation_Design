using System.IO;
using System.Windows;
using GraduationDesign.App.Configuration;
using GraduationDesign.App.Services;
using GraduationDesign.App.ViewModels;

namespace GraduationDesign.App;

public partial class App : Application
{
    private MainViewModel? _mainViewModel;

    public App()
    {
        DispatcherUnhandledException += OnDispatcherUnhandledException;
        AppDomain.CurrentDomain.UnhandledException += OnCurrentDomainUnhandledException;
        TaskScheduler.UnobservedTaskException += OnUnobservedTaskException;
    }

    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        try
        {
            var configPath = Path.Combine(AppContext.BaseDirectory, "appsettings.json");
            var configuration = ConfigurationLoader.LoadOrCreate(configPath);
            var deviceCatalog = new DeviceCatalog(configuration.Devices);
            var storage = new JsonLineMeasurementStorage(configuration.Storage, AppContext.BaseDirectory);
            var parser = new MeasurementProtocolParser();
            var server = new TcpMeasurementServer(configuration.Listener, parser);

            _mainViewModel = new MainViewModel(configuration, deviceCatalog, storage, server, Dispatcher);

            var mainWindow = new MainWindow(_mainViewModel);
            MainWindow = mainWindow;
            mainWindow.Show();

            _mainViewModel.StartAsync().GetAwaiter().GetResult();
        }
        catch (Exception exception)
        {
            MessageBox.Show(
                $"程序启动失败：{exception.Message}",
                "启动失败",
                MessageBoxButton.OK,
                MessageBoxImage.Error);

            Shutdown(-1);
        }
    }

    protected override void OnExit(ExitEventArgs e)
    {
        if (_mainViewModel is not null)
        {
            _mainViewModel.StopAsync().GetAwaiter().GetResult();
        }

        base.OnExit(e);
    }

    private void OnDispatcherUnhandledException(object sender, System.Windows.Threading.DispatcherUnhandledExceptionEventArgs e)
    {
        ShowFatalError("界面线程异常", e.Exception);
        e.Handled = true;
    }

    private void OnCurrentDomainUnhandledException(object sender, UnhandledExceptionEventArgs e)
    {
        if (e.ExceptionObject is Exception exception)
        {
            ShowFatalError("未处理异常", exception);
        }
    }

    private void OnUnobservedTaskException(object? sender, UnobservedTaskExceptionEventArgs e)
    {
        ShowFatalError("后台任务异常", e.Exception);
        e.SetObserved();
    }

    private static void ShowFatalError(string title, Exception exception)
    {
        MessageBox.Show(
            $"{title}：{exception.Message}",
            "程序异常",
            MessageBoxButton.OK,
            MessageBoxImage.Error);
    }
}
