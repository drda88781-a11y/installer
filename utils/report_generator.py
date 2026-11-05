from typing import Any
# utils/report_generator.py
"""
ماژول تولید فایل گزارش Stimulsoft (.mrt) و خروجی قابل چاپ صورت‌جلسه نصب سپهریار
Stimulsoft Reports (.mrt) template generator and printable handover report renderer
"""

import base64
import datetime
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import QDialog, QMessageBox

from config.settings import (
    APP_NAME_FA,
    APP_VERSION,
    SQL_INSTANCE_NAME,
    APP_LOGO_REPORT_PNG,
    APP_LOGO_CIRCLE_PNG,
    APP_LOGO_PNG,
)
from app_logging.app_logger import logger
from packages.product_catalog import get_product_by_id


def get_logo_base64() -> str:
    """
    دریافت رشته Base64 لوگوی رسمی زرین سپهریار جهت درج پایدار در سربرگ HTML و قالب استیمول‌سافت
    """
    candidates = [
        APP_LOGO_REPORT_PNG,
        APP_LOGO_CIRCLE_PNG,
        APP_LOGO_PNG,
        Path(__file__).resolve().parent.parent / "assets" / "images" / "logo_report.png",
        Path(__file__).resolve().parent.parent / "assets" / "images" / "logo_circle.png",
        Path(__file__).resolve().parent.parent / "assets" / "images" / "logo.png",
    ]
    for c in candidates:
        if c.exists():
            try:
                with open(c, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            except Exception:
                pass
    return ""


def generate_installation_mrt(data: Dict[str, any], output_path: Path) -> Path:
    """
    تولید فایل رسمی الگو و گزارش Stimulsoft Reports (.mrt) کاملاً سازگار با نگارش 2013.2.1700
    همراه با نشان رسمی سپهریار در سربرگ، بدون خطای Index was outside the bounds of the array
    """
    technician_name = data.get("technician_name", "کارشناس استقرار سپهریار")
    customer_name = data.get("customer_name", "مشتری محترم")
    install_date = data.get("install_date", datetime.date.today().strftime("%Y/%m/%d"))
    install_time = data.get("install_time", datetime.datetime.now().strftime("%H:%M"))
    install_path = data.get("install_path", "D:\\SEPEHRYAR")
    sql_instance = data.get("sql_instance", SQL_INSTANCE_NAME)
    products_list = data.get("products", [])
    hardware_summary = data.get("hardware_summary", "")

    products_str = " ، ".join(products_list) if products_list else "حسابداری سپهریار"
    logo_base64 = get_logo_base64()
    report_guid = uuid.uuid4().hex

    # فرمت‌های استاندارد و دقیق TextOptions استیمول‌سافت 2013 با 8 پارامتر الزامی و کاما انتهایی
    # جهت جلوگیری از خطای Index was outside the bounds of the array در StiTextOptionsHelper
    text_opt_nowrap = "HotkeyPrefix=None, LineLimit=False, RightToLeft=True, Trimming=None, WordWrap=False, Angle=0, FirstTabOffset=40, DistanceBetweenTabs=20,"
    text_opt_wrap = "HotkeyPrefix=None, LineLimit=False, RightToLeft=True, Trimming=None, WordWrap=True, Angle=0, FirstTabOffset=40, DistanceBetweenTabs=20,"

    image_tag = f"<Image>{logo_base64}</Image>" if logo_base64 else "<Image />"

    # ساختار کاملاً معتبر و سازگار با موتور Stimulsoft Reports.Net 2013.2.1700
    mrt_content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<StiSerializer version="1.02" type="Net" application="StiReport">
  <Dictionary Ref="1" type="Dictionary" isKey="true">
    <BusinessObjects isList="true" count="0" />
    <Databases isList="true" count="0" />
    <DataSources isList="true" count="0" />
    <Relations isList="true" count="0" />
    <Report isRef="0" />
    <Variables isList="true" count="0" />
  </Dictionary>
  <EngineVersion>EngineV2</EngineVersion>
  <GlobalizationStrings isList="true" count="0" />
  <MetaTags isList="true" count="0" />
  <Pages isList="true" count="1">
    <Page1 Ref="2" type="Page" isKey="true">
      <Border>All;Black;2;Solid;False;4;Black</Border>
      <Brush>Transparent</Brush>
      <Components isList="true" count="1">
        <ReportTitleBand1 Ref="3" type="ReportTitleBand" isKey="true">
          <Brush>Transparent</Brush>
          <ClientRectangle>0,0.4,19,26.5</ClientRectangle>
          <Components isList="true" count="7">
            <!-- 1. نشان زرین رسمی سپهریار در سربرگ گزارش -->
            <ImageLogo Ref="4" type="Image" isKey="true">
              <AspectRatio>True</AspectRatio>
              <Brush>Transparent</Brush>
              <ClientRectangle>16.2,0.4,2.4,2.4</ClientRectangle>
              <Conditions isList="true" count="0" />
              {image_tag}
              <Margins>0,0,0,0</Margins>
              <Name>ImageLogo</Name>
              <Page isRef="2" />
              <Parent isRef="3" />
              <Stretch>True</Stretch>
            </ImageLogo>

            <!-- 2. عنوان اصلی -->
            <HeaderTitle Ref="5" type="Text" isKey="true">
              <Brush>Transparent</Brush>
              <ClientRectangle>0.5,0.4,15.5,1.2</ClientRectangle>
              <Conditions isList="true" count="0" />
              <Font>B Titr,16,Bold</Font>
              <HorAlignment>Center</HorAlignment>
              <Margins>0,0,0,0</Margins>
              <Name>HeaderTitle</Name>
              <Page isRef="2" />
              <Parent isRef="3" />
              <Text>صورت‌جلسه تحویل و راه‌اندازی نرم‌افزار حسابداری سپهریار</Text>
              <TextBrush>Black</TextBrush>
              <TextOptions>{text_opt_nowrap}</TextOptions>
              <Type>Expression</Type>
              <VertAlignment>Center</VertAlignment>
            </HeaderTitle>

            <!-- 3. زیرعنوان -->
            <SubTitle Ref="6" type="Text" isKey="true">
              <Brush>Transparent</Brush>
              <ClientRectangle>0.5,1.6,15.5,0.8</ClientRectangle>
              <Conditions isList="true" count="0" />
              <Font>B Nazanin,11,Bold</Font>
              <HorAlignment>Center</HorAlignment>
              <Margins>0,0,0,0</Margins>
              <Name>SubTitle</Name>
              <Page isRef="2" />
              <Parent isRef="3" />
              <Text>نسخه نرم‌افزار: {APP_VERSION}  |  تاریخ ثبت: {install_date}  |  ساعت: {install_time}</Text>
              <TextBrush>[185:142:74]</TextBrush>
              <TextOptions>{text_opt_nowrap}</TextOptions>
              <Type>Expression</Type>
              <VertAlignment>Center</VertAlignment>
            </SubTitle>

            <!-- 4. کادر مشخصات تحویل -->
            <Box1 Ref="7" type="Panel" isKey="true">
              <Border>All;Black;1;Solid;False;4;Black</Border>
              <Brush>[250:248:242]</Brush>
              <ClientRectangle>0.5,3.0,18,3.6</ClientRectangle>
              <Components isList="true" count="5">
                <LblCust Ref="8" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>10,0.3,7.5,0.8</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,11,Bold</Font>
                  <HorAlignment>Right</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>LblCust</Name>
                  <Page isRef="2" />
                  <Parent isRef="7" />
                  <Text>نام کارفرما / خریدار: {customer_name}</Text>
                  <TextBrush>Black</TextBrush>
                  <TextOptions>{text_opt_nowrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Center</VertAlignment>
                </LblCust>
                <LblTech Ref="9" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>0.5,0.3,9,0.8</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,11,Bold</Font>
                  <HorAlignment>Right</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>LblTech</Name>
                  <Page isRef="2" />
                  <Parent isRef="7" />
                  <Text>مسئول نصب و استقرار: {technician_name}</Text>
                  <TextBrush>Black</TextBrush>
                  <TextOptions>{text_opt_nowrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Center</VertAlignment>
                </LblTech>
                <LblPath Ref="10" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>10,1.3,7.5,0.8</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,10</Font>
                  <HorAlignment>Right</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>LblPath</Name>
                  <Page isRef="2" />
                  <Parent isRef="7" />
                  <Text>مسیر نصب: {install_path}</Text>
                  <TextBrush>Black</TextBrush>
                  <TextOptions>{text_opt_nowrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Center</VertAlignment>
                </LblPath>
                <LblSql Ref="11" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>0.5,1.3,9,0.8</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,10</Font>
                  <HorAlignment>Right</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>LblSql</Name>
                  <Page isRef="2" />
                  <Parent isRef="7" />
                  <Text>پایگاه داده: {sql_instance} (فعال و تست‌شده)</Text>
                  <TextBrush>Black</TextBrush>
                  <TextOptions>{text_opt_nowrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Center</VertAlignment>
                </LblSql>
                <LblProds Ref="12" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>0.5,2.3,17,0.8</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,10,Bold</Font>
                  <HorAlignment>Right</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>LblProds</Name>
                  <Page isRef="2" />
                  <Parent isRef="7" />
                  <Text>بسته‌های نصب‌شده: {products_str}</Text>
                  <TextBrush>[185:142:74]</TextBrush>
                  <TextOptions>{text_opt_nowrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Center</VertAlignment>
                </LblProds>
              </Components>
              <Conditions isList="true" count="0" />
              <Name>Box1</Name>
              <Page isRef="2" />
              <Parent isRef="3" />
            </Box1>

            <!-- 5. چک‌لیست اعتبارسنجی -->
            <LblCheckHeader Ref="13" type="Text" isKey="true">
              <Brush>Transparent</Brush>
              <ClientRectangle>0.5,7.0,18,0.8</ClientRectangle>
              <Conditions isList="true" count="0" />
              <Font>B Titr,11,Bold</Font>
              <HorAlignment>Right</HorAlignment>
              <Margins>0,0,0,0</Margins>
              <Name>LblCheckHeader</Name>
              <Page isRef="2" />
              <Parent isRef="3" />
              <Text>چک‌لیست بررسی مؤلفه‌ها و صحت نصب:</Text>
              <TextBrush>Black</TextBrush>
              <TextOptions>{text_opt_nowrap}</TextOptions>
              <Type>Expression</Type>
              <VertAlignment>Center</VertAlignment>
            </LblCheckHeader>

            <!-- 6. جزئیات چک‌لیست -->
            <CheckText Ref="14" type="Text" isKey="true">
              <Border>All;Black;1;Solid;False;4;Black</Border>
              <Brush>Transparent</Brush>
              <ClientRectangle>0.5,8.0,18,8.5</ClientRectangle>
              <Conditions isList="true" count="0" />
              <Font>B Nazanin,10</Font>
              <HorAlignment>Right</HorAlignment>
              <Margins>6,6,6,6</Margins>
              <Name>CheckText</Name>
              <Page isRef="2" />
              <Parent isRef="3" />
              <Text>✓ ایجاد پوشه‌های چهارگانه ریشه (SEPEHRYAR.Setup | SEPEHRYAR.Data | SEPEHRYAR.Backup | SEPEHRYAR.Update)
✓ انتقال کامل فایل‌های Setup و گزارش‌سازهای سیستمی
✓ ثبت و پیکربندی فونت‌های فارسی (Arad و IRANSans) و ران‌تایم‌های Crystal Reports و Stimulsoft
✓ اتصال موفقیت‌آمیز به سرویس و اینستنس پایگاه داده {sql_instance}
✓ استقرار پکیج کامل فایل‌های اجرایی، گزارش‌ها، DLLها و فایل‌های پیکربندی
✓ ایجاد میانبرهای استاندارد دسکتاپ و منوی استارت ویندوز
✓ تست اجرای اولیه نرم‌افزار و اعتبارسنجی نهایی عملکرد سیستم

مشخصات سخت‌افزاری میزبان: {hardware_summary}</Text>
              <TextBrush>Black</TextBrush>
              <TextOptions>{text_opt_wrap}</TextOptions>
              <Type>Expression</Type>
              <VertAlignment>Top</VertAlignment>
            </CheckText>

            <!-- 7. کادر تعهدات و امضاها -->
            <BoxSign Ref="15" type="Panel" isKey="true">
              <Border>All;Black;1;Solid;False;4;Black</Border>
              <Brush>[250:250:250]</Brush>
              <ClientRectangle>0.5,17.5,18,8.0</ClientRectangle>
              <Components isList="true" count="3">
                <SignTerms Ref="16" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>0.5,0.4,17,2.0</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,9</Font>
                  <HorAlignment>Right</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>SignTerms</Name>
                  <Page isRef="2" />
                  <Parent isRef="15" />
                  <Text>تأییدیه تحویل: بدین‌وسیله کارفرما صحت عملکرد، راه‌اندازی و تحویل بسته‌های نرم‌افزاری فوق را تأیید نموده و آموزش‌های مقدماتی را دریافت کرده است. اطلاعات ورود و دسترسی در اختیار ایشان قرار گرفت.</Text>
                  <TextBrush>[60:60:60]</TextBrush>
                  <TextOptions>{text_opt_wrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Top</VertAlignment>
                </SignTerms>

                <SignCustomer Ref="17" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>10,3.0,7,4.2</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,10,Bold</Font>
                  <HorAlignment>Center</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>SignCustomer</Name>
                  <Page isRef="2" />
                  <Parent isRef="15" />
                  <Text>نام و امضای خریدار / مدیر مجموعه:
{customer_name}

مهر و امضا: .............................</Text>
                  <TextBrush>Black</TextBrush>
                  <TextOptions>{text_opt_nowrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Top</VertAlignment>
                </SignCustomer>

                <SignTech Ref="18" type="Text" isKey="true">
                  <Brush>Transparent</Brush>
                  <ClientRectangle>1,3.0,7,4.2</ClientRectangle>
                  <Conditions isList="true" count="0" />
                  <Font>B Nazanin,10,Bold</Font>
                  <HorAlignment>Center</HorAlignment>
                  <Margins>0,0,0,0</Margins>
                  <Name>SignTech</Name>
                  <Page isRef="2" />
                  <Parent isRef="15" />
                  <Text>مسئول نصب و استقرار سپهریار:
{technician_name}

مهر و امضا: .............................</Text>
                  <TextBrush>Black</TextBrush>
                  <TextOptions>{text_opt_nowrap}</TextOptions>
                  <Type>Expression</Type>
                  <VertAlignment>Top</VertAlignment>
                </SignTech>
              </Components>
              <Conditions isList="true" count="0" />
              <Name>BoxSign</Name>
              <Page isRef="2" />
              <Parent isRef="3" />
            </BoxSign>

          </Components>
          <Conditions isList="true" count="0" />
          <Name>ReportTitleBand1</Name>
          <Page isRef="2" />
          <Parent isRef="2" />
        </ReportTitleBand1>
      </Components>
      <Conditions isList="true" count="0" />
      <Margins>1,1,1,1</Margins>
      <Name>Page1</Name>
      <PageHeight>29.7</PageHeight>
      <PageWidth>21</PageWidth>
      <PaperSize>A4</PaperSize>
      <Report isRef="0" />
      <Watermark Ref="19" type="Stimulsoft.Report.Components.StiWatermark" isKey="true">
        <Font>Arial,100</Font>
        <TextBrush>[50:0:0:0]</TextBrush>
      </Watermark>
    </Page1>
  </Pages>
  <PrinterSettings Ref="20" type="Stimulsoft.Report.Print.StiPrinterSettings" isKey="true" />
  <ReferencedAssemblies isList="true" count="8">
    <value>System.Dll</value>
    <value>System.Drawing.Dll</value>
    <value>System.Windows.Forms.Dll</value>
    <value>System.Data.Dll</value>
    <value>System.Xml.Dll</value>
    <value>Stimulsoft.Controls.Dll</value>
    <value>Stimulsoft.Base.Dll</value>
    <value>Stimulsoft.Report.Dll</value>
  </ReferencedAssemblies>
  <ReportAlias>صورت‌جلسه نصب سپهریار</ReportAlias>
  <ReportChanged>{datetime.datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')}</ReportChanged>
  <ReportCreated>{datetime.datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')}</ReportCreated>
  <ReportFile>{str(output_path)}</ReportFile>
  <ReportGuid>{report_guid}</ReportGuid>
  <ReportName>Report</ReportName>
  <ReportUnit>Centimeters</ReportUnit>
  <ReportVersion>2013.2.1700</ReportVersion>
  <Script>using System;
using System.Drawing;
using System.Windows.Forms;
using System.Data;
using Stimulsoft.Controls;
using Stimulsoft.Base.Drawing;
using Stimulsoft.Report;
using Stimulsoft.Report.Dialogs;
using Stimulsoft.Report.Components;

namespace Reports
{{
    public class Report : Stimulsoft.Report.StiReport
    {{
        public Report()
        {{
            this.InitializeComponent();
        }}
        #region StiReport Designer generated code - do not modify
		#endregion StiReport Designer generated code - do not modify
    }}
}}
</Script>
  <ScriptLanguage>CSharp</ScriptLanguage>
  <Styles isList="true" count="0" />
</StiSerializer>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(mrt_content)

    logger.log("REPORT", "GENERATE_MRT", "SUCCESS", f"فایل قالب استیمول‌سافت همراه با لوگو ایجاد شد: {output_path}")
    return output_path


def render_printable_html(data: Dict[str, any]) -> str:
    """
    تولید نسخه HTML فرمت‌شده رسمی با سربرگ زرین و نشان اختصاصی سپهریار (استاندارد چاپ A4)
    """
    technician_name = data.get("technician_name", "کارشناس استقرار سپهریار")
    customer_name = data.get("customer_name", "مشتری محترم")
    install_date = data.get("install_date", datetime.date.today().strftime("%Y/%m/%d"))
    install_time = data.get("install_time", datetime.datetime.now().strftime("%H:%M"))
    install_path = data.get("install_path", "D:\\SEPEHRYAR")
    sql_instance = data.get("sql_instance", SQL_INSTANCE_NAME)
    products_list = data.get("products", [])
    hardware_summary = data.get("hardware_summary", "")

    # تولید شماره سریال رسمی صورت‌جلسه
    serial_no = f"SPY-{datetime.datetime.now().strftime('%Y%m%d')}-{datetime.datetime.now().strftime('%H%M%S')}"

    logo_b64 = get_logo_base64()
    logo_tag = f'<img src="data:image/png;base64,{logo_b64}" width="76" height="76" style="border-radius: 38px; border: 2px solid #D8A84E; display: block;" />' if logo_b64 else '<div style="width:76px;height:76px;border-radius:38px;background:#141720;border:2px solid #D8A84E;"></div>'

    products_badges = "".join([f"<span class='badge'>{p}</span>" for p in products_list])

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
    body {{
        font-family: 'B Nazanin', 'Vazirmatn', 'Tahoma', sans-serif;
        direction: rtl;
        text-align: right;
        margin: 15px;
        color: #111;
        background: #fff;
    }}
    .container {{
        border: 2px solid #181B24;
        padding: 24px;
        border-radius: 10px;
        background: #fff;
        position: relative;
    }}
    .gold-top-bar {{
        height: 6px;
        background: #D8A84E;
        border-radius: 6px 6px 0 0;
        margin: -24px -24px 20px -24px;
    }}
    .header-table {{
        width: 100%;
        border-collapse: collapse;
        border-bottom: 2px solid #D8A84E;
        padding-bottom: 12px;
        margin-bottom: 18px;
    }}
    .header-table td {{
        vertical-align: middle;
    }}
    .header-title-box {{
        text-align: center;
        padding: 0 10px;
    }}
    .header-title-box h1 {{
        margin: 0;
        font-size: 20px;
        color: #11141C;
        font-family: 'B Titr', 'Vazirmatn', 'Tahoma', sans-serif;
    }}
    .header-title-box .corp-name {{
        font-size: 13px;
        font-weight: bold;
        color: #B98E4A;
        margin-top: 4px;
    }}
    .header-title-box .sub {{
        font-size: 11.5px;
        color: #555;
        margin-top: 3px;
    }}
    .header-meta {{
        font-size: 11.5px;
        color: #333;
        line-height: 1.8;
        text-align: left;
    }}
    .info-table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 16px;
        background: #FAFAFA;
        border-radius: 6px;
    }}
    .info-table td {{
        padding: 9px 12px;
        border: 1px solid #E5E7EB;
        font-size: 12.5px;
    }}
    .info-table td.label {{
        font-weight: bold;
        width: 20%;
        background: #F4F5F7;
        color: #2D3748;
    }}
    .badge {{
        display: inline-block;
        background: #D8A84E;
        color: #0E1015;
        font-weight: bold;
        padding: 3px 9px;
        border-radius: 4px;
        margin-left: 6px;
        font-size: 11.5px;
        border: 1px solid #ECC867;
    }}
    .checklist {{
        border: 1px solid #E2E8F0;
        border-right: 4px solid #D8A84E;
        padding: 14px 18px;
        margin-bottom: 18px;
        background: #FAFAFA;
        font-size: 12.5px;
        line-height: 1.85;
        border-radius: 4px;
    }}
    .checklist h3 {{
        margin-top: 0;
        margin-bottom: 8px;
        font-size: 14px;
        color: #11141C;
        font-family: 'B Titr', 'Vazirmatn', sans-serif;
    }}
    .signatures {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 20px;
    }}
    .signatures td {{
        width: 50%;
        text-align: center;
        vertical-align: top;
        padding: 10px 14px;
    }}
    .sign-box {{
        border: 1px dashed #9CA3AF;
        background: #FCFCFD;
        min-height: 100px;
        margin-top: 8px;
        border-radius: 6px;
        padding: 10px;
    }}
    .footer-note {{
        text-align: center;
        font-size: 10.5px;
        color: #718096;
        margin-top: 12px;
        border-top: 1px solid #E5E7EB;
        padding-top: 6px;
    }}
</style>
</head>
<body>
<div class="container">
    <div class="gold-top-bar"></div>

    <!-- سربرگ رسمی با نشان اختصاصی سپهریار -->
    <table class="header-table">
        <tr>
            <td style="width: 85px; text-align: right;">
                {logo_tag}
            </td>
            <td class="header-title-box">
                <h1>صورت‌جلسه رسمی تحویل و راه‌اندازی نرم‌افزار</h1>
                <div class="corp-name">گروه نرم‌افزاری سپهریار — سامانه‌های یکپارچه مالی و رستورانی</div>
                <div class="sub">تأییدیه استقرار سیستم، پیکربندی پایگاه داده و تحویل مؤلفه‌ها (نسخه {APP_VERSION})</div>
            </td>
            <td style="width: 200px;" class="header-meta">
                <div><b>شماره سند:</b> {serial_no}</div>
                <div><b>تاریخ ثبت:</b> {install_date}</div>
                <div><b>ساعت تحویل:</b> {install_time}</div>
                <div><b>وضعیت:</b> <span style="color: #10B981; font-weight: bold;">تحویل موفقیت‌آمیز ✓</span></div>
            </td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <td class="label">نام خریدار / کارفرما:</td>
            <td><b>{customer_name}</b></td>
            <td class="label">مسئول استقرار سپهریار:</td>
            <td><b>{technician_name}</b></td>
        </tr>
        <tr>
            <td class="label">تاریخ و ساعت نصب:</td>
            <td>{install_date} — ساعت {install_time}</td>
            <td class="label">سرویس پایگاه داده:</td>
            <td>{sql_instance} (فعال و تست‌شده)</td>
        </tr>
        <tr>
            <td class="label">مسیر نصب فایل‌ها:</td>
            <td colspan="3"><code style="font-family: Consolas, monospace; background: #EEE; padding: 2px 6px; border-radius: 4px;">{install_path}</code></td>
        </tr>
        <tr>
            <td class="label">بسته‌های نصب‌شده:</td>
            <td colspan="3">{products_badges}</td>
        </tr>
    </table>

    <div class="checklist">
        <h3>چک‌لیست تحویل و تأیید سلامت مؤلفه‌ها:</h3>
        <div>☑ ایجاد ساختار چهارگانه SEPEHRYAR (SEPEHRYAR.Setup | SEPEHRYAR.Data | SEPEHRYAR.Backup | SEPEHRYAR.Update)</div>
        <div>☑ استقرار کامل فایل‌های اجرایی، کتابخانه‌های کمکی، DLLها، ران‌تایم‌ها و قالب‌های پیش‌فرض گزارش</div>
        <div>☑ ثبت و نصب فونت‌های فارسی (Arad و IRANSans) و ران‌تایم‌های Crystal Reports و Stimulsoft</div>
        <div>☑ راه‌اندازی و اعتبارسنجی اتصال به سرویس Microsoft SQL Server با اینستنس {sql_instance}</div>
        <div>☑ ایجاد میانبرهای استاندارد دسکتاپ و منوی استارت ویندوز با آیکون رسمی سپهریار</div>
        <div>☑ اجرای آزمایشی نرم‌افزار، صحت‌سنجی کامل سیستم و تحویل نام کاربری و رمز عبور اولیه</div>
        <div style="margin-top:6px; font-size:11px; color:#666;">مشخصات سخت‌افزاری میزبان: {hardware_summary}</div>
    </div>

    <table class="signatures">
        <tr>
            <td>
                <b>تأیید و امضای کارفرما / مدیر مجموعه</b>
                <div style="font-size:11.5px; color:#555; margin-top:3px;">بدین‌وسیله تحویل نرم‌افزار و آموزش‌های لازم تأیید می‌گردد.</div>
                <div class="sign-box">
                    <div style="font-size:12px; font-weight:bold; margin-top:8px;">{customer_name}</div>
                    <div style="margin-top:35px; font-size:11px; color:#888;">مهر و امضا: .......................................</div>
                </div>
            </td>
            <td>
                <b>تأیید و امضای کارشناس استقرار سپهریار</b>
                <div style="font-size:11.5px; color:#555; margin-top:3px;">صحت نصب و راه‌اندازی مؤلفه‌ها تأیید می‌شود.</div>
                <div class="sign-box">
                    <div style="font-size:12px; font-weight:bold; margin-top:8px;">{technician_name}</div>
                    <div style="margin-top:35px; font-size:11px; color:#888;">مهر و امضا: .......................................</div>
                </div>
            </td>
        </tr>
    </table>

    <div class="footer-note">
        این سند رسمی صورت‌جلسه تحویل نرم‌افزار حسابداری سپهریار بوده و به همراه فایل الگو (.mrt) در پوشه Setup بایگانی می‌گردد.
    </div>
</div>
</body>
</html>
"""


def show_print_preview_dialog(data: Dict[str, any], parent=None):
    """
    نمایش پیش‌نمایش چاپ رسمی ویندوز با قابلیت پرینت مستقیم روی چاپگر یا خروجی PDF
    """
    html_content = render_printable_html(data)
    doc = QTextDocument()
    doc.setHtml(html_content)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)

    def handle_print(p):
        doc.print_(p)

    preview_dialog = QPrintPreviewDialog(printer, parent)
    preview_dialog.setWindowTitle("پیش‌نمایش چاپ صورت‌جلسه نصب سپهریار")
    preview_dialog.resize(950, 750)
    preview_dialog.paintRequested.connect(handle_print)
    preview_dialog.exec()

