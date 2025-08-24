name: Auto Presensi

on:
  workflow_dispatch:
    inputs:
      force_mode:
        description: "Mode presensi (check_in / check_out)"
        required: true
        default: "check_in"
  schedule:
    - cron: "30 22 * * 0-5"  # 05:30 WIB check-in
    - cron: "5 9 * * 0-5"    # 16:05 WIB check-out

jobs:
  presensi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.x'

      - name: Install dependencies
        run: pip install selenium

      - name: Run Presensi
        env:
          USER1_USERNAME: ${{ secrets.USER1_USERNAME }}
          USER1_PASSWORD: ${{ secrets.USER1_PASSWORD }}
          USER2_USERNAME: ${{ secrets.USER2_USERNAME }}
          USER2_PASSWORD: ${{ secrets.USER2_PASSWORD }}
          FORCE_MODE: ${{ github.event.inputs.force_mode || '' }}
        run: python main.py

      - name: Upload artifacts (logs & screenshots)
        uses: actions/upload-artifact@v4
        with:
          name: presensi-artifacts
          path: artifacts/
