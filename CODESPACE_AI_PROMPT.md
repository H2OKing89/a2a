# AI Assistant Prompt for ABS Metadata PR

Copy and paste this into your GitHub Codespace AI chat, and attach the 3 markdown files:

---

I'm working on a PR for Audiobookshelf to fix missing FFmpeg metadata extraction. I've done a complete investigation and have attached 3 documentation files with my findings.

**Context:**
I analyzed an audiobook's metadata and discovered that Audiobookshelf's FFprobe parsing is missing critical fields that FFmpeg provides. Specifically:

1. **`sample_rate`** - FFprobe returns "44100" (as string), but ABS extracts `null`
2. **`profile`** - FFprobe returns "xHE-AAC" (Extended High Efficiency AAC), but ABS doesn't extract it at all
3. Other optional fields: `sample_fmt`, `bits_per_sample`, `nb_frames`

**What I need help with:**

Please review the attached documentation files:

- `ABS_INVESTIGATION_REPORT.md` - Complete findings and analysis
- `METADATA_EXTRACTION_GUIDE.md` - Investigation methodology  
- `QUICK_REFERENCE.md` - Quick lookup reference

Then help me:

1. **Find the FFprobe parsing code** in the Audiobookshelf repository
   - Likely in: `server/utils/audioProbe.js` or similar
   - Look for where audio streams are parsed from FFprobe output

2. **Locate the AudioFile model/schema**
   - Where audio file metadata fields are defined
   - Database model that needs new fields added

3. **Implement the fix** to extract missing fields:

   ```javascript
   audioFile.sampleRate = parseInt(audioStream.sample_rate) || null
   audioFile.profile = audioStream.profile || null
   ```

4. **Update the database model** to include the new fields:
   - `sampleRate: INTEGER`
   - `profile: STRING`

5. **Create a database migration** if needed

6. **Help me test** the changes using the test data I have:
   - Item ID: `089b48d1-d3a1-4a77-b9b5-eb19ea68af0e`
   - Expected `sampleRate: 44100`
   - Expected `profile: "xHE-AAC"`

**Important Details:**

- The audiobook uses xHE-AAC codec at 118 kbps - a modern high-efficiency codec
- This is critical metadata for quality assessment
- FFprobe clearly provides this data, ABS just isn't extracting it
- See the raw FFprobe data comparison in the attached docs

Please start by helping me locate the relevant files in the repository structure, then guide me through implementing the fix step by step.

---

**Attached Files (tag these in the chat):**

1. `./dev/ABS_INVESTIGATION_REPORT.md`
2. `./dev/METADATA_EXTRACTION_GUIDE.md`
3. `./dev/QUICK_REFERENCE.md`
