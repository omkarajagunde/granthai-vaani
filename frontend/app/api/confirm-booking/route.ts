import { type NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { name, phone, address, appointmentType, preferredDate, preferredTime, persona, voice } = body

    // Simulate booking confirmation processing
    const bookingId = `BK${Date.now().toString(36).toUpperCase()}`

    const confirmation = {
      success: true,
      bookingId,
      status: "confirmed",
      customerInfo: {
        name,
        phone,
        address,
        email: body.email || `${name.toLowerCase().replace(" ", ".")}@email.com`,
      },
      appointmentDetails: {
        type: appointmentType,
        preferredDate,
        preferredTime,
        estimatedDuration: "30 minutes",
      },
      aiAssistant: {
        persona,
        voice,
        callScheduled: true,
      },
      nextSteps: [
        "AI assistant will call you shortly",
        "Appointment confirmation will be sent via SMS",
        "Calendar invite will be emailed",
      ],
      timestamp: new Date().toISOString(),
    }

    return NextResponse.json(confirmation)
  } catch (error) {
    return NextResponse.json({ success: false, error: "Failed to confirm booking" }, { status: 500 })
  }
}
