from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import inch
from xml.etree.ElementTree import ElementTree
import Image, re, sys

class HocrConverter():
  """
  A class for converting documents to/from the hOCR format.
  
  For details of the hOCR format, see:
  
    http://docs.google.com/View?docid=dfxcv4vc_67g844kf
    
  See also:
  
    http://code.google.com/p/hocr-tools/
  
  Basic usage:
  
  Create a PDF from an hOCR file and an image:
    
    hocr = HocrConverter("path/to/hOCR/file")
    hocr.to_pdf("path/to/image/file", "path/to/output/file")
  
  """
  def __init__(self, hocrFileName = None):
    self.hocr = None
    self.xmlns = ''
    self.boxPattern = re.compile('bbox((\s+\d+){4})')
    if hocrFileName is not None:
      self.parse_hocr(hocrFileName)
      
  def __str__(self):
    """
    Return the textual content of the HTML body
    """
    if self.hocr is None:
      return ''
    body =  self.hocr.find(".//%sbody"%(self.xmlns))
    if body:
      return self._get_element_text(body).encode('utf-8') # XML gives unicode
    else:
      return ''
  
  def _get_element_text(self, element):
    """
    Return the textual content of the element and its children
    """
    text = ''
    if element.text is not None:
      text = text + element.text
    for child in element.getchildren():
      text = text + self._get_element_text(child)
    if element.tail is not None:
      text = text + element.tail
    return text
    
  def element_coordinates(self, element):
    """
    Returns a tuple containing the coordinates of the bounding box around
    an element
    """
    out = (0,0,0,0)
    if 'title' in element.attrib:
      matches = self.boxPattern.search(element.attrib['title'])
      if matches:
        coords = matches.group(1).split()
        out = (int(coords[0]),int(coords[1]),int(coords[2]),int(coords[3]))
    return out
    
  def parse_hocr(self, hocrFileName):
    """
    Reads an XML/XHTML file into an ElementTree object
    """
    self.hocr = ElementTree()
    self.hocr.parse(hocrFileName)
    
    # if the hOCR file has a namespace, ElementTree requires its use to find elements
    matches = re.match('({.*})html', self.hocr.getroot().tag)
    if matches:
      self.xmlns = matches.group(1)
    else:
      self.xmlns = ''
      
  def to_pdf(self, imageFileName, outFileName, fontname="Courier", fontsize=8):
    """
    Creates a PDF file with an image superimposed on top of the text.
    
    Text is positioned according to the bounding box of the lines in
    the hOCR file.
    
    The image need not be identical to the image used to create the hOCR file.
    It can be scaled, have a lower resolution, different color mode, etc.
    """
    if self.hocr is None:
      # warn that no text will be embedded in the output PDF
      print "Warning: No hOCR file specified. PDF will be image-only."
      
    im = Image.open(imageFileName)
    imwidthpx, imheightpx = im.size
    if 'dpi' in im.info:
      width = float(im.size[0])/im.info['dpi'][0]
      height = float(im.size[1])/im.info['dpi'][1]
    else:
      # we have to make a reasonable guess
      # set to None for now and try again using info from hOCR file
      width = height = None
      
      
    ocr_dpi = (300, 300) # a default, in case we can't find it
    
    # get dimensions of the OCR, which may not match the image
    if self.hocr is not None:
      for div in self.hocr.findall(".//%sdiv"%(self.xmlns)):
        if div.attrib['class'] == 'ocr_page':
          coords = self.element_coordinates(div)
          ocrwidth = coords[2]-coords[0]
          ocrheight = coords[3]-coords[1]
          if width is None:
            # no dpi info with the image
            # assume OCR was done at 300 dpi
            width = ocrwidth/300
            height = ocrheight/300
          ocr_dpi = (ocrwidth/width, ocrheight/height)
          break # there shouldn't be more than one, and if there is, we don't want it
            
    if width is None:
      # no dpi info with the image, and no help from the hOCR file either
      # this will probably end up looking awful, so issue a warning
      print "Warning: DPI unavailable for image %s. Assuming 96 DPI."%(imageFileName)
      width = float(im.size[0])/96
      height = float(im.size[1])/96
      
    # create the PDF file
    pdf = Canvas(outFileName, pagesize=(width*inch, height*inch), pageCompression=1) # page size in points (1/72 in.)
    
    # put the image on the page, scaled to fill the page
    pdf.drawInlineImage(im, 0, 0, width=width*inch, height=height*inch)
    
    if self.hocr is not None:
      for line in self.hocr.findall(".//%sspan"%(self.xmlns)):
        if line.attrib['class'] == 'ocr_line':
          coords = self.element_coordinates(line)
          text = pdf.beginText()
          text.setFont(fontname, fontsize)
          text.setTextRenderMode(3) # invisible
          
          # set cursor to bottom left corner of line bbox (adjust for dpi)
          text.setTextOrigin((float(coords[0])/ocr_dpi[0])*inch, (height*inch)-(float(coords[3])/ocr_dpi[1])*inch)
          
          # scale the width of the text to fill the width of the line's bbox
          text.setHorizScale((((float(coords[2])/ocr_dpi[0]*inch)-(float(coords[0])/ocr_dpi[0]*inch))/pdf.stringWidth(line.text.rstrip(), fontname, fontsize))*100)
          
          # write the text to the page
          text.textLine(line.text.rstrip())
          pdf.drawText(text)
    
    # finish up the page and save it
    pdf.showPage()
    pdf.save()
  
  def to_text(self, outFileName):
    """
    Writes the textual content of the hOCR body to a file.
    """
    f = open(outFileName, "w")
    f.write(self.__str__())
    f.close()

if __name__ == "__main__":
  if len(sys.argv) < 4:
    print 'Usage: python HocrConverter.py inputHocrFile inputImageFile outputPdfFile'
    sys.exit(1)
  hocr = HocrConverter(sys.argv[1])
  hocr.to_pdf(sys.argv[2], sys.argv[3])