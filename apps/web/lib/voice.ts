"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface RecognitionEventLike {
  results: { 0: { 0: { transcript: string } }; length: number };
}

interface RecognitionLike {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  onresult: ((event: RecognitionEventLike) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type RecognitionCtor = new () => RecognitionLike;

export function speak(text: string, enabled = true, lang = "hi-IN"): void {
  if (!enabled || typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const synth = window.speechSynthesis;
  synth.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = 0.9;
  utterance.pitch = 1;
  const voices = synth.getVoices();
  const preferred =
    voices.find((voice) => voice.lang?.toLowerCase().startsWith("hi")) ??
    voices.find((voice) => voice.lang?.toLowerCase().includes("in"));
  if (preferred) utterance.voice = preferred;
  synth.speak(utterance);
}

export function stopSpeaking(): void {
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

export function useRecognition(onResult: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognition = useRef<RecognitionLike | null>(null);
  const callback = useRef(onResult);

  useEffect(() => {
    callback.current = onResult;
  }, [onResult]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const ctor = (window as unknown as { SpeechRecognition?: RecognitionCtor; webkitSpeechRecognition?: RecognitionCtor })
      .SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: RecognitionCtor }).webkitSpeechRecognition;
    if (!ctor) {
      setSupported(false);
      return;
    }
    const instance = new ctor();
    instance.lang = "hi-IN";
    instance.interimResults = false;
    instance.continuous = false;
    instance.maxAlternatives = 1;
    instance.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript ?? "";
      if (transcript.trim()) callback.current(transcript.trim());
    };
    instance.onend = () => setListening(false);
    instance.onerror = () => {
      setListening(false);
      setError("Mic nahi chal raha — type karke bhejiye.");
    };
    recognition.current = instance;
    setSupported(true);
    return () => {
      instance.onend = null;
      instance.onresult = null;
      instance.onerror = null;
      instance.abort();
      recognition.current = null;
    };
  }, []);

  const start = useCallback(() => {
    setError(null);
    if (!recognition.current) {
      setError("Is browser mein speech recognition nahi hai. Chrome par kholiye.");
      return;
    }
    try {
      recognition.current.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, []);

  const stop = useCallback(() => {
    recognition.current?.stop();
    setListening(false);
  }, []);

  return { listening, supported, error, start, stop };
}
