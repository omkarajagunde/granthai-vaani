"use client"

import type React from "react"
import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import {
  Mic,
  MicOff,
  Play,
  CheckCircle,
  Phone,
  Smile,
  FileText,
  Volume2,
  Send,
  Loader2,
  Sparkles,
  Zap,
} from "lucide-react"

interface PersonaType {
  id: string
  name: string
  icon: React.ComponentType<{ className?: string }>
  description: string
  color: string
  gradient: string
}

interface VoiceType {
  id: string
  name: string
  accent: string
  icon: React.ComponentType<{ className?: string }>
  preview: string
}

interface CapturedData {
  name?: string
  address?: string
  phone?: string
  email?: string
  appointmentType?: string
  preferredDate?: string
  preferredTime?: string
}

interface TranscriptChunk {
  id: string
  text: string
  timestamp: number
  confidence: number
}

class Response {
  text: null
  audioData: null
  endOfTurn: null
  constructor(data: any) {
    this.text = null;
    this.audioData = null;
    this.endOfTurn = null;

    if (data.text) {
      this.text = data.text
    }

    if (data.audio) {
      this.audioData = data.audio;
    }
  }
}

export default function GranthAICallPro() {
  const [selectedPersona, setSelectedPersona] = useState<string>("")
  const [selectedVoice, setSelectedVoice] = useState<string>("")
  const [isRecording, setIsRecording] = useState(false)
  const [transcriptChunks, setTranscriptChunks] = useState<TranscriptChunk[]>([])
  const [capturedData, setCapturedData] = useState<CapturedData>({})
  const [isProcessing, setIsProcessing] = useState(false)
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [isCallInitiated, setIsCallInitiated] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [contactForm, setContactForm] = useState({
    fullName: "",
    email: "",
    company: "",
    message: "",
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitSuccess, setSubmitSuccess] = useState(false)
  const [assistantMessage, setAssistantMessage] = useState("")
  const [playingVoice, setPlayingVoice] = useState<string>("")
  const [windowWidth, setWindowWidth] = useState(0)

  const waveformRef = useRef<HTMLDivElement>(null)
  let pcmData: number[] = []
  let webSocket: WebSocket;
  let initialized = false
  let audioInputContext: AudioContext;
  let workletNode: AudioWorkletNode

  // Handle window width for responsive particles
  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth)
    }

    if (typeof window !== "undefined") {
      setWindowWidth(window.innerWidth)
      window.addEventListener("resize", handleResize)
      return () => window.removeEventListener("resize", handleResize)
    }
  }, [])

  const personas: PersonaType[] = [
    {
      id: "pathology",
      name: "Pathology Test Agent",
      icon: Phone,
      description: "Book lab tests and medical appointments",
      color: "#D8E9A8",
      gradient: "from-green-400 to-emerald-500",
    }
  ]

  const voices: VoiceType[] = [
    {
      id: "mohan",
      name: "Mohan",
      accent: "English",
      icon: Mic,
      preview: "Hello! I'm Mohan, your friendly assistant.",
    }
  ]

  const steps = ["Select Persona", "Choose Voice", "Start talking"]

  const initializeAudioContext = async () => {
    if (initialized) return;

    audioInputContext = new (window.AudioContext)({ sampleRate: 24000 });
    await audioInputContext.audioWorklet.addModule("pcm-processor.js");
    workletNode = new AudioWorkletNode(audioInputContext, "pcm-processor");
    workletNode.connect(audioInputContext.destination);
    initialized = true;
  }

  const injestAudioChuckToPlay = async (base64AudioChunk: any) => {

    const base64ToArrayBuffer = (base64: any) => {
      const binaryString = window.atob(base64);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }
      return bytes.buffer;
    }

    const convertPCM16LEToFloat32 = (pcmData: any) => {
      const inputArray = new Int16Array(pcmData);
      const float32Array = new Float32Array(inputArray.length);

      for (let i = 0; i < inputArray.length; i++) {
        float32Array[i] = inputArray[i] / 32768;
      }

      return float32Array;
    }


    try {
      if (!initialized) {
        await initializeAudioContext();
      }

      if (audioInputContext.state === "suspended") {
        await audioInputContext.resume();
      }
      const arrayBuffer = base64ToArrayBuffer(base64AudioChunk);
      const float32Data = convertPCM16LEToFloat32(arrayBuffer);

      workletNode.port.postMessage(float32Data);
    } catch (error) {
      console.error("Error processing audio chunk:", error);
    }
  }

  const receiveMessage = (event: any) => {
    const messageData = JSON.parse(event.data);
    const response = new Response(messageData);

    if (response.audioData) {
      injestAudioChuckToPlay(response.audioData);
    }
  }

  const connect = () => {

    webSocket = new WebSocket("wss://granthai-vaani-production.up.railway.app");

    webSocket.onclose = (event) => {
      console.log("websocket closed: ", event);
      alert("Connection closed");
    };

    webSocket.onerror = (event) => {
      console.log("websocket error: ", event);
    };

    webSocket.onopen = (event) => {
      console.log("websocket open: ", event);
    };

    webSocket.onmessage = receiveMessage;
  }

  const sendVoiceMessage = (b64PCM: any) => {
    if (webSocket == null) {
      console.log("websocket not initialized");
      return;
    }

    let payload = {
      realtime_input: {
        media_chunks: [{
          mime_type: "audio/pcm",
          data: b64PCM,
        }
        ],
      },
    };

    webSocket.send(JSON.stringify(payload));
    console.log("sent: ", payload);
  }

  const recordChunk = () => {
    const buffer = new ArrayBuffer(pcmData.length * 2);
    const view = new DataView(buffer);
    pcmData.forEach((value, index) => {
      view.setInt16(index * 2, value, true);
    });


    const base64 = btoa(
      // @ts-ignore
      String.fromCharCode.apply(null, new Uint8Array(buffer))
    );

    sendVoiceMessage(base64);
    pcmData = [];
  }

  const startAudioInput = async () => {
    let audioContext = new AudioContext({
      sampleRate: 16000,
    });

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
      },
    });

    const source = audioContext.createMediaStreamSource(stream);
    let processor = audioContext.createScriptProcessor(4096, 1, 1);

    const floatTo16BitPCM = (float32Array: any) => {
      const buffer = new ArrayBuffer(float32Array.length * 2);
      const view = new DataView(buffer);
      for (let i = 0; i < float32Array.length; i++) {
        let s = Math.max(-1, Math.min(1, float32Array[i]));
        view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true); // little-endian
      }
      return buffer;
    }

    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);
      const pcm16 = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        pcm16[i] = inputData[i] * 0x7fff;
      }

      pcmData.push(...pcm16);

      // const pcm = floatTo16BitPCM(inputData);
      // let binary = '';
      // const bytes = new Uint8Array(pcm);
      // for (let i = 0; i < bytes.byteLength; i++) {
      //   binary += String.fromCharCode(bytes[i]);
      // }
      // sendVoiceMessage(btoa(binary))
      // recordChunk()
    };

    source.connect(processor);
    processor.connect(audioContext.destination);

    let interval = setInterval(recordChunk, 1500);
  }

  // Simulate voice recording and real-time transcription
  const handleStartRecording = async () => {
    if (!selectedPersona || !selectedVoice) {
      setAssistantMessage("Please select a persona and voice first! 🎭🎤")
      return
    }

    setIsRecording(true)
    setIsProcessing(true)

    connect()
    startAudioInput()
  }

  const handleConfirmBooking = async () => {
    setCurrentStep(5)
    setAssistantMessage("Initiating your call... 📞")

    // Simulate API call to confirm booking
    try {
      const response = await fetch("/api/confirm-booking", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...capturedData,
          persona: selectedPersona,
          voice: selectedVoice,
          timestamp: new Date().toISOString(),
        }),
      })

      if (response.ok) {
        // Simulate Twilio call initiation
        await initiateCall()
      }
    } catch (error) {
      console.log("Simulated API call - booking confirmed")
      await initiateCall()
    }
  }

  const initiateCall = async () => {
    try {
      const response = await fetch("/api/initiate-call", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phone: capturedData.phone,
          persona: selectedPersona,
          voice: selectedVoice,
          appointmentDetails: capturedData,
        }),
      })

      setIsCallInitiated(true)
      setCurrentStep(5)
      setAssistantMessage("Call initiated successfully! You'll receive a call shortly. 🎉")
    } catch (error) {
      console.log("Simulated Twilio call initiated")
      setIsCallInitiated(true)
      setCurrentStep(5)
      setAssistantMessage("Call initiated successfully! You'll receive a call shortly. 🎉")
    }
  }

  const handleVoicePreview = async (voiceId: string) => {
    setPlayingVoice(voiceId)
    // Simulate audio preview
    setTimeout(() => setPlayingVoice(""), 2000)
  }

  const resetSession = () => {
    setSelectedPersona("")
    setSelectedVoice("")
    setIsRecording(false)
    setTranscriptChunks([])
    setCapturedData({})
    setIsProcessing(false)
    setShowConfirmation(false)
    setIsCallInitiated(false)
    setCurrentStep(0)
    setAssistantMessage("Welcome back! Let's start fresh. 🌟")
  }

  const handleContactSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(contactForm),
      })

      setTimeout(() => {
        setIsSubmitting(false)
        setSubmitSuccess(true)
        setContactForm({ fullName: "", email: "", company: "", message: "" })
        setTimeout(() => setSubmitSuccess(false), 3000)
      }, 2000)
    } catch (error) {
      console.log("Simulated contact form submission")
      setTimeout(() => {
        setIsSubmitting(false)
        setSubmitSuccess(true)
        setContactForm({ fullName: "", email: "", company: "", message: "" })
        setTimeout(() => setSubmitSuccess(false), 3000)
      }, 2000)
    }
  }

  // Animated waveform effect
  useEffect(() => {
    if (isRecording && waveformRef.current) {
      const bars = waveformRef.current.children
      const animateWave = () => {
        Array.from(bars).forEach((bar, index) => {
          const height = Math.random() * 60 + 20
            ; (bar as HTMLElement).style.height = `${height}px`
            ; (bar as HTMLElement).style.opacity = `${0.6 + Math.random() * 0.4}`
        })
      }

      const interval = setInterval(animateWave, 100)
      return () => clearInterval(interval)
    }
  }, [isRecording])

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#195e40" }}>
      {/* Animated Background Particles */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        {typeof window !== "undefined" &&
          Array.from({ length: 20 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-2 h-2 bg-white/10 rounded-full"
              animate={{
                x: [0, windowWidth || 800],
                y: [0, 600],
                opacity: [0, 1, 0],
              }}
              transition={{
                duration: 10 + Math.random() * 10,
                repeat: Number.POSITIVE_INFINITY,
                delay: Math.random() * 5,
              }}
              style={{
                left: Math.random() * (windowWidth || 800),
                top: Math.random() * 200,
              }}
            />
          ))}
      </div>

      <div className="relative z-10 container mx-auto px-4 py-8">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-12">
          <motion.h1
            className="text-5xl md:text-6xl font-bold mb-4"
            style={{ color: "#D8E9A8" }}
            animate={{
              textShadow: [
                "0 0 20px rgba(216, 233, 168, 0.5)",
                "0 0 30px rgba(216, 233, 168, 0.8)",
                "0 0 20px rgba(216, 233, 168, 0.5)",
              ],
            }}
            transition={{ duration: 2, repeat: Number.POSITIVE_INFINITY }}
          >
            Vaani | वाणी
          </motion.h1>
          <motion.p
            className="text-xl text-white/80 max-w-3xl mx-auto"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            AI phone agents that sound human, speak any language, and work 24/7.
          </motion.p>
        </motion.div>

        {/* Progress Indicator */}
        <motion.div className="mb-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}>
          <div className="flex justify-center items-center space-x-4 mb-4">
            {steps.map((step, index) => (
              <motion.div
                key={index}
                className={`flex items-center space-x-2 ${index <= currentStep ? "text-white" : "text-white/40"}`}
                animate={{
                  scale: index === currentStep ? 1.1 : 1,
                  color: index <= currentStep ? "#D8E9A8" : "rgba(255,255,255,0.4)",
                }}
              >
                <div className={`w-3 h-3 rounded-full ${index <= currentStep ? "bg-green-400" : "bg-white/20"}`} />
                <span className="text-sm hidden md:block">{step}</span>
                {index < steps.length - 1 && (
                  <div className={`w-8 h-0.5 ${index < currentStep ? "bg-green-400" : "bg-white/20"}`} />
                )}
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Assistant Message */}
        <AnimatePresence>
          {assistantMessage && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="text-center mb-8"
            >
              <div className="inline-block bg-white/10 backdrop-blur-md rounded-full px-6 py-3">
                <span className="text-white font-medium">{assistantMessage}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="grid lg:grid-cols-3 gap-8 mb-12">
          {/* Persona Selection */}
          <motion.div
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.9 }}
            className="space-y-4"
          >
            <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
              <Sparkles className="mr-2 h-5 w-5" style={{ color: "#D8E9A8" }} />
              Choose Your Assistant
            </h3>
            {personas.map((persona, index) => (
              <motion.div
                key={persona.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1 + index * 0.1 }}
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                <Card
                  className={`cursor-pointer transition-all duration-300 border-2 ${selectedPersona === persona.id
                    ? "border-green-400 bg-white/20 shadow-lg shadow-green-400/20"
                    : "border-white/20 bg-white/10 hover:bg-white/15"
                    }`}
                  onClick={() => {
                    setSelectedPersona(persona.id)
                    setCurrentStep(Math.max(currentStep, 0))
                    setAssistantMessage(`Great choice! ${persona.name} selected. 🎯`)
                  }}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-lg bg-gradient-to-r ${persona.gradient}`}>
                        <persona.icon className="h-6 w-6 text-white" />
                      </div>
                      <div>
                        <h4 className="font-medium text-white">{persona.name}</h4>
                        <p className="text-sm text-white/70">{persona.description}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>

          {/* Central Voice Interaction */}
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 1.2 }}
            className="flex flex-col items-center justify-center space-y-6"
          >
            {/* Microphone Button */}
            <motion.div
              className="relative"
              animate={{
                scale: isRecording ? [1, 1.1, 1] : 1,
              }}
              transition={{ duration: 1, repeat: isRecording ? Number.POSITIVE_INFINITY : 0 }}
            >
              <motion.div
                className={`w-32 h-32 rounded-full flex items-center justify-center shadow-2xl cursor-pointer ${isRecording
                  ? "bg-gradient-to-br from-red-500 to-red-600"
                  : "bg-gradient-to-br from-green-500 to-emerald-600"
                  }`}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={isRecording ? () => setIsRecording(false) : handleStartRecording}
              >
                {isRecording ? <MicOff className="h-12 w-12 text-white" /> : <Mic className="h-12 w-12 text-white" />}
              </motion.div>

              {/* Aura Effect */}
              {isRecording && (
                <motion.div
                  className="absolute inset-0 rounded-full border-4 border-green-400"
                  animate={{
                    scale: [1, 1.5, 1],
                    opacity: [1, 0, 1],
                  }}
                  transition={{ duration: 1.5, repeat: Number.POSITIVE_INFINITY }}
                />
              )}
            </motion.div>

            {/* Waveform Animation */}
            <div ref={waveformRef} className="flex items-end justify-center space-x-1 h-20">
              {Array.from({ length: 25 }).map((_, i) => (
                <motion.div
                  key={i}
                  className="w-1 bg-gradient-to-t from-green-400 to-emerald-500 rounded-full"
                  style={{
                    height: isRecording ? "20px" : "8px",
                    opacity: isRecording ? 1 : 0.3,
                  }}
                  animate={{
                    height: isRecording ? [8, 60, 8] : 8,
                  }}
                  transition={{
                    duration: 0.5 + Math.random() * 0.5,
                    repeat: isRecording ? Number.POSITIVE_INFINITY : 0,
                    delay: i * 0.05,
                  }}
                />
              ))}
            </div>

            <Button
              onClick={isRecording ? () => setIsRecording(false) : handleStartRecording}
              size="lg"
              className={`px-8 py-3 text-lg font-semibold transition-all duration-300 ${isRecording
                ? "bg-red-500 hover:bg-red-600"
                : "bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                }`}
              disabled={isProcessing}
            >
              {isProcessing ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Processing...
                </>
              ) : isRecording ? (
                <>
                  <MicOff className="mr-2 h-5 w-5" />
                  Stop Recording
                </>
              ) : (
                <>
                  <Mic className="mr-2 h-5 w-5" />
                  Start Talking
                </>
              )}
            </Button>

            {/* Reset Button */}
            {(transcriptChunks.length > 0 || isCallInitiated) && (
              <Button onClick={resetSession} variant="outline" className="border-white/30 text-white hover:bg-white/10">
                <Zap className="mr-2 h-4 w-4" />
                Start New Session
              </Button>
            )}
          </motion.div>

          {/* Voice Selection */}
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 1.4 }}
            className="space-y-4"
          >
            <h3 className="text-xl font-semibold text-white mb-4 flex items-center">
              <Volume2 className="mr-2 h-5 w-5" style={{ color: "#D8E9A8" }} />
              Select Voice
            </h3>
            {voices.map((voice, index) => (
              <motion.div
                key={voice.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1.5 + index * 0.1 }}
                whileHover={{ scale: 1.02, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                <Card
                  className={`cursor-pointer transition-all duration-300 border-2 ${selectedVoice === voice.id
                    ? "border-blue-400 bg-white/20 shadow-lg shadow-blue-400/20"
                    : "border-white/20 bg-white/10 hover:bg-white/15"
                    }`}
                  onClick={() => {
                    setSelectedVoice(voice.id)
                    setCurrentStep(Math.max(currentStep, 1))
                    setAssistantMessage(`Perfect! ${voice.name} voice selected. 🎤`)
                  }}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <voice.icon className="h-6 w-6" style={{ color: "#D8E9A8" }} />
                        <div>
                          <h4 className="font-medium text-white">{voice.name}</h4>
                          <p className="text-sm text-white/70">{voice.accent}</p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleVoicePreview(voice.id)
                        }}
                        className="text-white hover:bg-white/10"
                      >
                        {playingVoice === voice.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </div>

        {/* Live Transcription Console */}
        <AnimatePresence>
          {transcriptChunks.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="mb-8"
            >
              <Card className="bg-black/80 border-green-400/30">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-green-400 flex items-center">
                      <span className="w-2 h-2 bg-green-400 rounded-full mr-2 animate-pulse"></span>
                      Live Transcription Console
                    </h3>
                    <span className="text-green-400/70 text-sm font-mono">
                      {transcriptChunks.length} chunks processed
                    </span>
                  </div>
                  <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm max-h-40 overflow-y-auto">
                    {transcriptChunks.map((chunk, index) => (
                      <motion.div
                        key={chunk.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.1 }}
                        className="mb-1"
                      >
                        <span className="text-gray-500 text-xs mr-2">
                          [{new Date(chunk.timestamp).toLocaleTimeString()}]
                        </span>
                        <span className="text-green-400">{chunk.text}</span>
                        <span className="text-yellow-400 text-xs ml-2">({(chunk.confidence * 100).toFixed(0)}%)</span>
                      </motion.div>
                    ))}
                    {isRecording && (
                      <motion.div
                        animate={{ opacity: [1, 0.5, 1] }}
                        transition={{ duration: 1, repeat: Number.POSITIVE_INFINITY }}
                        className="text-green-400"
                      >
                        ▋ Listening...
                      </motion.div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Captured Data JSON View */}
        <AnimatePresence>
          {Object.keys(capturedData).length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="mb-8"
            >
              <Card className="bg-gray-900/90 border-blue-400/30">
                <CardContent className="p-6">
                  <h3 className="text-lg font-semibold text-blue-400 mb-4 flex items-center">
                    <span className="w-2 h-2 bg-blue-400 rounded-full mr-2 animate-pulse"></span>
                    Extracted Information (Live Session)
                  </h3>
                  <div className="bg-black rounded-lg p-4 font-mono text-sm">
                    <div className="text-gray-500 mb-2">// Real-time data extraction</div>
                    <pre className="text-blue-400">{JSON.stringify(capturedData, null, 2)}</pre>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Footer */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2.5 }}
          className="text-center py-8 mt-16"
        >
          <p className="text-white/60">
            © 2025 Vaani | वाणी. Revolutionizing appointment booking with AI voice assistants.
          </p>
        </motion.footer>
      </div>
    </div>
  )
}
