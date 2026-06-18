/*
 * File: photo_cleanup.sh
 * Project: rzierke-site
 * Created Date: 2026-05-25
 * Author: Reagan Zierke
 * Email: reaganzierke@gmail.com
 * -----
 * Last Modified: 2026-06-17 22:10:50
 * Modified By: Reagan Zierke
 * -----
 * Description: Script to convert all .webp, .jpg, and .jpeg images in the current directory to .png format and then delete the original files.
 */


// Linux
find . -type f \( -name "*.webp" -o -name "*.jpg" -o -name "*.jpeg" \) -exec mogrify -format png {} \; && find . -type f \( -name "*.webp" -o -name "*.jpg" -o -name "*.jpeg" \) -delete

// Windows (PowerShell)
Get-ChildItem -File | Where-Object { $_.Extension -match '\.(jpg|jpeg|webp)$' } | % { magick $_.FullName "$($_.BaseName).png"; if ($?) { Remove-Item $_.FullName } }



# JPG/JPEG/WEBP via ImageMagick
Get-ChildItem -File |
Where-Object { $_.Extension -match '\.(jpg|jpeg|webp)$' } |
ForEach-Object {
    magick $_.FullName "$($_.BaseName).png"
    if ($LASTEXITCODE -eq 0) {
        Remove-Item $_.FullName
    }
}

# AVIF via FFmpeg
Get-ChildItem *.avif | ForEach-Object {
    $output = "$($_.BaseName).png"

    ffmpeg -y -i $_.FullName $output

    if (Test-Path $output) {
        Remove-Item $_.FullName
    }
}

