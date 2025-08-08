set "TARGET_DIR=C:\Users\Andrew\Downloads\serverOutput\@user\@job"

for %%f in ("%TARGET_DIR%\*.exr") do (
    echo Processing: %%f
    magick "%%f" "%%~dpnf.png"
    if !errorlevel! equ 0 (
        echo Successfully converted: %%~nxf
        del "%%f"
        echo Deleted original: %%~nxf
    ) else (
        echo Failed to convert: %%~nxf
    )
)