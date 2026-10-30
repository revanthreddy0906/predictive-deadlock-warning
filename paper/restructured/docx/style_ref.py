"""Restyle pandoc's reference.docx to an IEEE-like look: Times New Roman 10 pt, black
headings, centred captions, booktabs-style tables, boxed findings."""
import re, shutil, zipfile, sys

src, dst = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(src)
s = zin.read("word/styles.xml").decode()

TNR = '<w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman" />'
s = re.sub(r"<w:rFonts w:asciiTheme=[^>]*/>", TNR, s)
s = re.sub(r'<w:color w:val="[0-9A-F]+"[^>]*/>', '<w:color w:val="000000" />', s)
s = s.replace('<w:sz w:val="24" />\n          <w:szCs w:val="24" />\n          <w:lang', '<w:sz w:val="20" />\n          <w:szCs w:val="20" />\n          <w:lang')
s = re.sub(r'(<w:rPrDefault>\s*<w:rPr>.*?)<w:sz w:val="24" />\s*<w:szCs w:val="24" />',
           r'\1<w:sz w:val="20" /><w:szCs w:val="20" />', s, flags=re.S)
s = s.replace('<w:pPrDefault>\n      <w:pPr>\n        <w:spacing w:after="200" />',
              '<w:pPrDefault>\n      <w:pPr>\n        <w:spacing w:after="0" />')

def restyle(sid, ppr=None, rpr=None):
    global s
    m = re.search(r'(<w:style [^>]*w:styleId="' + sid + r'".*?)(</w:style>)', s, re.S)
    block = m.group(1)
    block = re.sub(r"<w:pPr>.*?</w:pPr>|<w:pPr ?/>", "", block, flags=re.S) if ppr is not None else block
    block = re.sub(r"<w:rPr>.*?</w:rPr>|<w:rPr ?/>", "", block, flags=re.S) if rpr is not None else block
    if ppr is not None:
        block += f"<w:pPr>{ppr}</w:pPr>"
    if rpr is not None:
        block += f"<w:rPr>{rpr}</w:rPr>"
    s = s[:m.start()] + block + m.group(2) + s[m.end():]

restyle("BodyText", ppr='<w:spacing w:before="0" w:after="120" w:line="252" w:lineRule="auto" /><w:jc w:val="both" />')
restyle("Title", ppr='<w:spacing w:before="0" w:after="200" /><w:jc w:val="center" />', rpr=TNR + '<w:sz w:val="44" /><w:szCs w:val="44" />')
restyle("Author", ppr='<w:keepNext /><w:spacing w:before="0" w:after="20" /><w:jc w:val="center" />', rpr=TNR + '<w:sz w:val="22" /><w:szCs w:val="22" />')
restyle("Date", ppr='<w:keepNext /><w:spacing w:before="60" w:after="200" /><w:jc w:val="center" />', rpr=TNR + '<w:i /><w:sz w:val="20" /><w:szCs w:val="20" />')
restyle("AbstractTitle", ppr='<w:keepNext /><w:spacing w:before="120" w:after="40" /><w:jc w:val="left" />', rpr=TNR + '<w:b /><w:i /><w:sz w:val="18" /><w:szCs w:val="18" />')
restyle("Abstract", ppr='<w:spacing w:before="0" w:after="160" /><w:jc w:val="both" />', rpr=TNR + '<w:b /><w:sz w:val="18" /><w:szCs w:val="18" />')
restyle("Heading1", ppr='<w:keepNext /><w:keepLines /><w:spacing w:before="240" w:after="120" /><w:jc w:val="center" /><w:outlineLvl w:val="0" />',
        rpr=TNR + '<w:smallCaps /><w:color w:val="000000" /><w:sz w:val="20" /><w:szCs w:val="20" />')
restyle("Heading2", ppr='<w:keepNext /><w:keepLines /><w:spacing w:before="160" w:after="80" /><w:outlineLvl w:val="1" />',
        rpr=TNR + '<w:i /><w:color w:val="000000" /><w:sz w:val="20" /><w:szCs w:val="20" />')
restyle("Caption", ppr='<w:spacing w:before="60" w:after="120" /><w:jc w:val="center" />', rpr=TNR + '<w:sz w:val="16" /><w:szCs w:val="16" />')
restyle("TableCaption", ppr='<w:keepNext /><w:spacing w:before="160" w:after="60" /><w:jc w:val="center" />', rpr=TNR + '<w:smallCaps /><w:sz w:val="16" /><w:szCs w:val="16" />')
restyle("ImageCaption", ppr='<w:spacing w:before="40" w:after="160" /><w:jc w:val="left" />', rpr=TNR + '<w:sz w:val="16" /><w:szCs w:val="16" />')
restyle("Compact", ppr='<w:spacing w:before="0" w:after="0" />')
restyle("BlockText", ppr='<w:pBdr><w:top w:val="single" w:sz="6" w:space="4" w:color="000000" /><w:left w:val="single" w:sz="6" w:space="4" w:color="000000" />'
        '<w:bottom w:val="single" w:sz="6" w:space="4" w:color="000000" /><w:right w:val="single" w:sz="6" w:space="4" w:color="000000" /></w:pBdr>'
        '<w:spacing w:before="120" w:after="160" /><w:ind w:left="120" w:right="120" /><w:jc w:val="both" />')
restyle("Bibliography", ppr='<w:spacing w:before="0" w:after="40" /><w:ind w:left="400" w:hanging="400" /><w:jc w:val="both" />', rpr=TNR + '<w:sz w:val="16" /><w:szCs w:val="16" />')

# booktabs-like tables: rule above and below, rule under the header row, 8 pt text
m = re.search(r'(<w:style w:type="table" w:default="1" w:styleId="Table">.*?)(</w:style>)', s, re.S)
tbl = ('<w:style w:type="table" w:default="1" w:styleId="Table"><w:name w:val="Table" /><w:basedOn w:val="TableNormal" /><w:qFormat />'
       '<w:pPr><w:spacing w:before="0" w:after="0" /></w:pPr><w:rPr><w:sz w:val="16" /><w:szCs w:val="16" /></w:rPr>'
       '<w:tblPr><w:jc w:val="center" /><w:tblInd w:w="0" w:type="dxa" /><w:tblBorders><w:top w:val="single" w:sz="8" w:space="0" w:color="000000" />'
       '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000" /></w:tblBorders>'
       '<w:tblCellMar><w:top w:w="10" w:type="dxa" /><w:left w:w="80" w:type="dxa" /><w:bottom w:w="10" w:type="dxa" /><w:right w:w="80" w:type="dxa" /></w:tblCellMar></w:tblPr>'
       '<w:tblStylePr w:type="firstRow"><w:rPr><w:b /></w:rPr><w:tcPr><w:tcBorders><w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000" /></w:tcBorders><w:vAlign w:val="bottom" /></w:tcPr></w:tblStylePr></w:style>')
s = s[:m.start()] + tbl + s[m.end():]

shutil.copy(src, dst)
zout = zipfile.ZipFile(dst + ".tmp", "w", zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = s.encode() if item.filename == "word/styles.xml" else zin.read(item.filename)
    zout.writestr(item, data)
zout.close()
shutil.move(dst + ".tmp", dst)
print("styled reference written")
