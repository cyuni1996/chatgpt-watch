param([ValidateSet('recognize','synthesize','status')][string]$Mode, [string]$Path)
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
if ($Mode -eq 'status') {
    $recognizers = @([System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | ForEach-Object { $_.Culture.Name })
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $voices = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Culture.Name })
    $synth.Dispose()
    @{recognition = ($recognizers -contains 'zh-CN'); synthesis = ($voices -contains 'zh-CN')} | ConvertTo-Json -Compress
} elseif ($Mode -eq 'synthesize') {
    $inputData = [Console]::In.ReadToEnd() | ConvertFrom-Json
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try {
        $synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, [System.Speech.Synthesis.VoiceAge]::NotSet, 0, [System.Globalization.CultureInfo]::GetCultureInfo('zh-CN'))
        $synth.SetOutputToWaveFile($Path, (New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)))
        $synth.Speak([string]$inputData.text)
    } finally { $synth.Dispose() }
    @{ok = $true} | ConvertTo-Json -Compress
} else {
    $engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine([System.Globalization.CultureInfo]::GetCultureInfo('zh-CN'))
    try {
        $engine.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
        $engine.SetInputToWaveFile($Path)
        $parts = @()
        $confidence = @()
        while ($true) {
            try {
                $result = $engine.Recognize([TimeSpan]::FromSeconds(5))
            } catch {
                # SAPI detaches file input at EOF. A subsequent Recognize call
                # throws InvalidOperationException instead of returning null.
                if ($_.Exception.InnerException -is [System.InvalidOperationException]) { break }
                throw
            }
            if ($null -eq $result) { break }
            $parts += $result.Text
            $confidence += $result.Confidence
        }
        @{text = ($parts -join ''); confidence = $confidence} | ConvertTo-Json -Compress
    } finally { $engine.Dispose() }
}
