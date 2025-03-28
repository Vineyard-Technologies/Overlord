using System.Windows;
using System.Windows.Controls;
using System.Diagnostics;
using System.Reflection;

namespace Overlord;

public partial class MainWindow : Window
{
    private bool noPrompt = true;
    string logSize = "500000000";
    private string scriptDirectory = System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
        "OneDrive",
        "repositories",
        "DAZScripts"
    );

    public MainWindow()
    {
        InitializeComponent();
        SetWindowTitle();
        AddFormElements();
    }

    private void SetWindowTitle()
    {
        string appName = "Overlord";
        string version = Assembly.GetExecutingAssembly().GetName().Version?.ToString() ?? "0.0.0.0";
        this.Title = $"{appName} v{version}";
    }

    private void AddFormElements()
    {
        // Checkbox for noPrompt
        CheckBox noPromptCheckBox = new CheckBox
        {
            Content = "No Prompt",
            Margin = new Thickness(10),
            IsChecked = noPrompt
        };
        noPromptCheckBox.Checked += (s, e) => noPrompt = true;
        noPromptCheckBox.Unchecked += (s, e) => noPrompt = false;

        // Label for log size
        TextBlock logSizeLabel = new TextBlock
        {
            Text = "Log file size (megabytes):",
            Margin = new Thickness(10)
        };

        // Textbox for log size
        TextBox logSizeTextBox = new TextBox
        {
            Text = "500", // Default value
            Margin = new Thickness(10),
            Width = 100
        };
        logSizeTextBox.TextChanged += (s, e) =>
        {
            if (int.TryParse(logSizeTextBox.Text, out int sizeInMb))
            {
                logSize = (sizeInMb * 1000000).ToString(); // Convert MB to bytes
            }
        };

        // Execute button
        Button executeButton = new Button
        {
            Content = "Start Rendering",
            Margin = new Thickness(10)
        };
        executeButton.Click += ExecuteButton_Click;

        MainContainer.Children.Add(noPromptCheckBox);
        MainContainer.Children.Add(logSizeLabel);
        MainContainer.Children.Add(logSizeTextBox);
        MainContainer.Children.Add(executeButton);
    }

    private void ExecuteButton_Click(object sender, RoutedEventArgs e)
    {
        Process process = new Process();
        process.StartInfo.FileName = "\"C:\\Program Files\\DAZ 3D\\DAZStudio4\\DAZStudio.exe\"";

        string masterRendererPath = System.IO.Path.Combine(scriptDirectory, "masterRenderer.dsa");

        process.StartInfo.Arguments = $"-scriptArg 1 -instanceName # -logSize {logSize} " + (noPrompt ? "-noPrompt " : "") + $"\"{masterRendererPath}\"";
        process.StartInfo.UseShellExecute = false;
        process.StartInfo.RedirectStandardOutput = true;
        process.StartInfo.RedirectStandardError = true;
        process.StartInfo.CreateNoWindow = false;

        process.Start();
    }
}