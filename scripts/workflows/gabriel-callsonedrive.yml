      - name: Build Daily Coaching Sheet (Markdown)
        run: |
          mkdir -p out/daily
          python scripts/build_daily_sheet.py \
            "out/${{ steps.dates.outputs.date_dir }}/manifest.json" \
            "out/${{ steps.dates.outputs.date_dir }}/transcripts" \
            "out/daily/Gabriel_${{ steps.dates.outputs.date_compact }}.md" \
            "Sales/Coaching/Gabriel"

      - name: Upload to OneDrive (audio, transcripts, daily sheet)
        env:
          RCLONE_CONFIG_OD_TYPE: onedrive
          RCLONE_CONFIG_OD_TOKEN: ${{ secrets.RCLONE_CONFIG_OD_TOKEN }}
        run: |
          # Daily sheet to /Coaching/Daily
          rclone copy "out/daily" "od:Sales/Coaching/Gabriel/Daily" --recursive -P
          # Day’s audio+transcripts to dated folder
          rclone copy "out/${{ steps.dates.outputs.date_dir }}" "od:Sales/Coaching/Gabriel/${{ steps.dates.outputs.date_dir }}" --recursive -P
