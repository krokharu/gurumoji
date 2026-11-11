def read_app_source(static):
    return "\n".join((static / name).read_text(encoding="utf-8") for name in ['app-transcription.js', 'app-progress.js', 'app-results.js', 'app-analysis.js', 'app-library.js', 'app-speakers.js', 'app.js'])
