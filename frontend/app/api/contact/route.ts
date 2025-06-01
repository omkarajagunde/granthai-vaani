import { type NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { fullName, email, company, message } = body

    // Simulate contact form processing
    const contactId = `CT${Date.now().toString(36).toUpperCase()}`

    const response = {
      success: true,
      contactId,
      status: "received",
      submittedData: {
        fullName,
        email,
        company,
        message,
        submittedAt: new Date().toISOString(),
      },
      autoResponse: {
        subject: "Thank you for your interest in GranthAI CallPro",
        message: "We have received your inquiry and will get back to you within 24 hours.",
        estimatedResponseTime: "24 hours",
      },
      nextSteps: [
        "Your inquiry has been forwarded to our sales team",
        "You will receive a confirmation email shortly",
        "A product specialist will contact you within 24 hours",
      ],
    }

    return NextResponse.json(response)
  } catch (error) {
    return NextResponse.json({ success: false, error: "Failed to process contact form" }, { status: 500 })
  }
}
