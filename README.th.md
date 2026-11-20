# Git FlowKit

**Skill สำหรับ Git Workflow, Conventional Commits และ Semantic Release ที่ใช้กฎของโปรเจกต์คุณ**

[English](README.md) · [Configuration](skills/git-flowkit/references/configuration.md) · [Release setup](skills/git-flowkit/references/releases.md)

รวมการตั้งชื่อ Branch, ตรวจ Commit, สร้าง PR/Merge Message, ปรับแต่ง Templates และ
วางแผนเวอร์ชันไว้ใน Agent Skill เดียว โดยไม่ผูกกับ API ของผู้ให้บริการ AI รายใด

> รุ่นเริ่มต้น ยังไม่ได้ประกาศ Stable Release การรองรับรูปแบบ Agent Skills ไม่ใช่
> หลักฐานว่าทดสอบใช้งานจริงกับทุก Agent แล้ว ส่วน Release Automation ต้องเปิดใช้งานเอง

[วิธีติดตั้งตาม agent และใช้งานผ่าน API client](skills/git-flowkit/references/compatibility.md#project-installation-by-host)

## ติดตั้ง

```bash
npx skills add whale-devx/git-flowkit-skills --skill git-flowkit
```

เลือก Agent ผ่านตัวติดตั้ง เพิ่ม `-g` เมื่อต้องการติดตั้งระดับผู้ใช้ ส่วน CLI ของ Skills
เป็นเครื่องมือภายนอก ไม่ใช่ npm package ที่โปรเจกต์นี้เผยแพร่

ตัวอย่างคำสั่งให้ Agent:

> ใช้ git-flowkit ตรวจ Repository นี้ อ่านกฎเดิม แล้วเตรียมชื่อ Branch, Commit,
> PR Description และ Release Preview ห้าม Merge หรือ Publish

## สิ่งที่ทำได้แล้ว

ตั้งชื่อและตรวจ Branch, ตรวจ Conventional Commits และ Breaking Changes, เลือก
Templates ตามลำดับความสำคัญ, สร้าง Config/Template แบบไม่เขียนทับไฟล์เดิม,
คำนวณ SemVer แบบ Preview สำหรับ Single Package และเตรียม Release Please Workflow
แบบต้องเปิดใช้งานเอง มีตัวตรวจ Merge Evidence แบบออฟไลน์ แต่ไม่มีคำสั่ง Merge จริง

ผู้ใช้แก้ไฟล์ JSON และ Markdown ได้เองทั้งหมด ทั้งระดับ Repository และ Global
ไฟล์ Config ที่ใช้จริงคือ `.git-flowkit.json` ไม่ใช่ YAML ที่เคยเสนอในช่วงออกแบบ

```bash
python skills/git-flowkit/scripts/flowkit.py init
python skills/git-flowkit/scripts/flowkit.py init --apply
python skills/git-flowkit/scripts/flowkit.py validate
```

`init` แสดง Preview ส่วน `--apply` สร้างเฉพาะไฟล์ที่ยังไม่มี จากนั้นเลือกไฟล์ Template
ใน `templates` ของ Config เมื่อคุณต้องการใช้แทน Template เดิมของ Repository

## Automatic Semantic Versioning

Release Please เป็นเจ้าของเวอร์ชันจริง ตัว CLI ทำเพียง Preview พร้อมเหตุผลจาก Commit
รองรับ PATCH/MINOR/MAJOR และนโยบายก่อน 1.0 แยกกัน ไม่ใช้ AI เดาเวอร์ชัน

การคำนวณ Monorepo, การยกเลิกผลของ Revert และการเลื่อน Prerelease เดิมให้ใช้ Native
Release Engine ส่วน CLI จะหยุดแทนการรายงานตัวเลขที่ไม่น่าเชื่อถือ

สำหรับ Repository นี้ ต้อง Merge งานตั้งค่าและตรวจ CI ก่อน แล้วให้ Maintainer ตั้ง
Repository Variable `FLOWKIT_RELEASE_ENABLED=true` จึงจะเริ่ม Automation ได้
รีโปกำหนดให้รุ่นแรกที่เข้าเกณฑ์ตามปกติเป็น `0.1.0` ส่วนรุ่นถัดไปคำนวณจากรุ่นก่อนหน้าและนโยบาย Commit ของโปรเจกต์
ยังไม่มีการ Publish npm/PyPI ดูขั้นตอนและข้อจำกัด Token ใน
[Release guide](skills/git-flowkit/references/releases.md)

## ตรวจสอบ

```bash
python -m unittest discover -s tests -v
python tools/validate_repo.py
```

ต้องมี Python 3.11+ และ Git ตัว Helper ใช้ Standard Library เท่านั้น ไม่มี Network
Request และไม่ทำ Commit, Push, Merge, Tag หรือ Publish เอง

อ่านขอบเขตทั้งหมดใน [README ภาษาอังกฤษ](README.md),
[Security](SECURITY.md) และ [Roadmap](ROADMAP.md)

ในสำเนา Git ของโครงการ ใช้ `python tools/install_smoke.py candidate` เพื่อทดสอบการติดตั้ง
และเรียกตัวช่วยจากตำแหน่งที่ติดตั้งจริง หรือใช้ `python tools/install_smoke.py main` เพื่อทดสอบ
จาก GitHub ต้องมี Node.js พร้อม npx, Python, Git และเข้าถึง npm registry ได้ การทดสอบ main
ต้องเข้าถึง GitHub และมีคอมมิตของ main ในเครื่องด้วย ทั้งสองคำสั่งใช้โครงการชั่วคราวและแสดง
คอมมิตกับตำแหน่งติดตั้ง หากเชื่อมต่อไม่ได้ ให้อ่านข้อผิดพลาดแล้วลองใหม่เมื่อเครือข่ายพร้อม
