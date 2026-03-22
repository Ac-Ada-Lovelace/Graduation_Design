using System.Windows;
using GraduationDesign.App.ViewModels;
using GraduationDesign.App.Views;

namespace GraduationDesign.App;

public partial class MainWindow : Window
{
    public MainWindow(MainViewModel viewModel)
    {
        InitializeComponent();
        DataContext = viewModel;
    }

    private void DeviceCard_Click(object sender, RoutedEventArgs e)
    {
        if ((sender as FrameworkElement)?.Tag is not DeviceViewModel device)
        {
            return;
        }

        var detailWindow = new DeviceDetailWindow(device)
        {
            Owner = this
        };

        detailWindow.Show();
    }

    private void OpenPacketDetail_Click(object sender, RoutedEventArgs e)
    {
        if ((sender as FrameworkElement)?.Tag is not PacketListItemViewModel packet)
        {
            return;
        }

        try
        {
            var detailWindow = new PacketDetailWindow(packet.Record)
            {
                Owner = this
            };

            detailWindow.Show();
        }
        catch (Exception exception)
        {
            MessageBox.Show(
                $"打开协议包详情失败：{exception.Message}",
                "打开失败",
                MessageBoxButton.OK,
                MessageBoxImage.Error);
        }
    }
}
