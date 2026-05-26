/*
 * File: photo_cleanup.sh
 * Project: rzierke-site
 * Created Date: 2026-05-25
 * Author: Reagan Zierke
 * Email: reaganzierke@gmail.com
 * -----
 * Last Modified: 2026-05-25 23:45:38
 * Modified By: Reagan Zierke
 * -----
 * Description: Script to convert all .webp, .jpg, and .jpeg images in the current directory to .png format and then delete the original files.
 */

find . -type f \( -name "*.webp" -o -name "*.jpg" -o -name "*.jpeg" \) -exec mogrify -format png {} \; && find . -type f \( -name "*.webp" -o -name "*.jpg" -o -name "*.jpeg" \) -delete