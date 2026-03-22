using System.Windows;
using GraduationDesign.App.ViewModels;

namespace GraduationDesign.App.Views;

public partial class DeviceDetailWindow : Window
{
    public DeviceDetailWindow(DeviceViewModel device)
    {
        InitializeComponent();
        DataContext = device;
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
