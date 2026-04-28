import os
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
import qrcode
from PIL import Image

def generate_certificate_pdf(user_name: str, course_title: str, completion_date: str, certificate_id: str, output_path: str):
    """
    Generates a high-quality PDF certificate for CourseForge.
    """
    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    width, height = landscape(A4)

    # 1. Background Gradient (Dark Theme)
    c.setFillColor(HexColor("#050511"))
    c.rect(0, 0, width, height, fill=1)

    # 2. Border
    c.setStrokeColor(HexColor("#7c3aed"))
    c.setLineWidth(5)
    c.rect(0.25*inch, 0.25*inch, width-0.5*inch, height-0.5*inch)

    # 3. Logo/Header
    c.setFont("Helvetica-Bold", 40)
    c.setFillColor(HexColor("#FFFFFF"))
    c.drawCentredString(width/2, height - 1.5*inch, "COURSEFORGE MASTER")
    
    c.setFont("Helvetica", 14)
    c.setFillColor(HexColor("#7c3aed"))
    c.drawCentredString(width/2, height - 2*inch, "PROOF OF NEURAL INDEXING")

    # 4. Recipient
    c.setFont("Helvetica", 20)
    c.setFillColor(HexColor("#AAAAAA"))
    c.drawCentredString(width/2, height/2 + 0.5*inch, "This certifies that")
    
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(HexColor("#FFFFFF"))
    c.drawCentredString(width/2, height/2 - 0.2*inch, user_name.upper())

    # 5. Course Info
    c.setFont("Helvetica", 18)
    c.setFillColor(HexColor("#AAAAAA"))
    c.drawCentredString(width/2, height/2 - 0.8*inch, f"has successfully forged mastery in")
    
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(HexColor("#7c3aed"))
    c.drawCentredString(width/2, height/2 - 1.3*inch, course_title)

    # 6. Date & ID
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor("#444444"))
    c.drawString(0.8*inch, 0.8*inch, f"DATE: {completion_date}")
    c.drawRightString(width - 0.8*inch, 0.8*inch, f"CERTIFICATE ID: {certificate_id}")

    # 7. QR Code for Verification
    qr_data = f"https://courseforge.ai/verify/{certificate_id}"
    qr = qrcode.QRCode(box_size=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="white", back_color="black")
    
    # Save temporary QR
    qr_path = "tmp_qr.png"
    qr_img.save(qr_path)
    c.drawImage(qr_path, width - 1.5*inch, 1*inch, width=0.8*inch, height=0.8*inch)
    
    c.save()
    
    # Clean up
    if os.path.exists(qr_path):
        os.remove(qr_path)

    return output_path
