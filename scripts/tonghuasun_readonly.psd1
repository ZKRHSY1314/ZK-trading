@{
    SchemaVersion = 1
    # Non-secret project launch settings. Plugin-managed credentials stay outside Git.
    ProductHome = 'D:\TonghuasunCodex'
    ExecutablePath = 'D:\同花顺软件\同花顺远航版\bin\happ.exe'
    # The local plugin is the project's preferred source, so the launcher must not
    # demote it. Sina and Tencent stay reachable as fallbacks inside the
    # tonghuasun_first chain, and a fallback is reported as a fallback.
    DailyBarSourcePolicy = 'tonghuasun_first'
}
