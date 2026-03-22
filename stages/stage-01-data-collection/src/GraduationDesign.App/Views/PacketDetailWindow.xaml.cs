using System.Windows;
using GraduationDesign.App.Models;
using GraduationDesign.App.ViewModels;

namespace GraduationDesign.App.Views;

public partial class PacketDetailWindow : Window
{
    public PacketDetailWindow(MeasurementRecord record)
    {
        InitializeComponent();
        DataContext = new PacketDetailViewModel(record);
    }
}
