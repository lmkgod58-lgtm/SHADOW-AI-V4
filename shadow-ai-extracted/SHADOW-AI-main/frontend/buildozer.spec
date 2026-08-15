[app]
title = Shadow AI
package.name = shadowai
package.domain = com.shadowai
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,mp4
version = 3.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0
android.api = 33
android.minapi = 21
android.ndk = 28c
android.archs = arm64-v8a
android.allow_backup = True
android.permissions = INTERNET,ACCESS_NETWORK_STATE

[buildozer]
log_level = 2
warn_on_root = 1
