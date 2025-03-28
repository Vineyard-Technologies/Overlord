using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;
using System.Reflection;

namespace Overlord;

/// <summary>
/// Interaction logic for MainWindow.xaml
/// </summary>
public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        SetWindowTitle();
    }

    private void SetWindowTitle()
    {
        string appName = "Overlord";
        string version = Assembly.GetExecutingAssembly().GetName().Version.ToString();
        this.Title = $"{appName} v{version}";
    }
}