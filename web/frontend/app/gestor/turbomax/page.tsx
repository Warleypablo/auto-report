"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import GestorShell from "../_shell";
import { gestorApi, type ChatMessage, type ClienteGestor } from "@/lib/api-gestor";

const WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "## TurboMax\n\n" +
    "Olá! Sou seu especialista em performance digital.\n\n" +
    "Posso te ajudar com:\n" +
    "• Análise de ROAS, CPL e métricas de qualquer cliente\n" +
    "• Diagnóstico de campanhas Meta Ads e Google Ads ao vivo\n" +
    "• Comparativos entre clientes da carteira\n" +
    "• Dicas técnicas de otimização\n\n" +
    "Por onde quer começar?",
};

// ── Markdown renderer ─────────────────────────────────────────────────────────

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") ? (
          <strong key={i} className="font-semibold text-[var(--ink)]">{p.slice(2, -2)}</strong>
        ) : (
          p
        ),
      )}
    </>
  );
}

function renderContent(text: string) {
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];
  let tableBuffer: string[] = [];
  let listBuffer: React.ReactNode[] = [];

  function flushTable() {
    if (tableBuffer.length < 2) {
      tableBuffer.forEach((l, i) => elements.push(<p key={`t${i}`} className="text-sm">{l}</p>));
      tableBuffer = [];
      return;
    }
    const [header, , ...rows] = tableBuffer;
    const cols = header.split("|").map((c) => c.trim()).filter(Boolean);
    elements.push(
      <div key={`table-${elements.length}`} className="my-3 overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              {cols.map((c, i) => (
                <th key={i} className="border border-[var(--rule-soft)] bg-[var(--paper-deep)] px-3 py-1.5 text-left font-medium text-[var(--muted)]">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} className="even:bg-[var(--paper-soft)]">
                {row.split("|").map((c) => c.trim()).filter(Boolean).map((cell, ci) => (
                  <td key={ci} className="border border-[var(--rule-soft)] px-3 py-1.5 text-[var(--ink)]">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    tableBuffer = [];
  }

  function flushList() {
    if (listBuffer.length === 0) return;
    elements.push(
      <ul key={`list-${elements.length}`} className="my-1 space-y-0.5 pl-1">
        {listBuffer}
      </ul>,
    );
    listBuffer = [];
  }

  lines.forEach((line, i) => {
    const isListLine = line.startsWith("• ") || line.startsWith("- ");
    if (!isListLine && listBuffer.length > 0) flushList();

    if (line.includes("|")) {
      tableBuffer.push(line);
      return;
    }
    if (tableBuffer.length) flushTable();

    if (line.startsWith("## ")) {
      elements.push(
        <p key={i} className="mb-1 mt-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--forest)] first:mt-0">
          {line.slice(3)}
        </p>,
      );
      return;
    }

    if (!line.trim()) {
      elements.push(<div key={i} className="h-2" />);
      return;
    }

    if (isListLine) {
      listBuffer.push(
        <li key={i} className="flex gap-2 text-sm">
          <span className="mt-[3px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[var(--forest)] opacity-60" />
          <span>{renderInline(line.slice(2))}</span>
        </li>,
      );
      return;
    }

    elements.push(
      <p key={i} className="text-sm leading-relaxed">
        {renderInline(line)}
      </p>,
    );
  });

  if (tableBuffer.length) flushTable();
  if (listBuffer.length) flushList();
  return <>{elements}</>;
}

// ── Agent avatar ──────────────────────────────────────────────────────────────

function AgentAvatar({ pulsing = false }: { pulsing?: boolean }) {
  return (
    <div className="relative flex-shrink-0">
      {pulsing && (
        <span className="absolute -inset-1.5 animate-ping rounded-xl bg-[var(--forest)] opacity-[0.12]" />
      )}
      <div
        className="flex h-9 w-9 items-center justify-center rounded-xl text-base text-white transition-all duration-500"
        style={{
          background: "var(--forest)",
          boxShadow: pulsing
            ? "0 0 22px rgba(52,211,153,0.5), 0 0 40px rgba(52,211,153,0.15)"
            : "0 0 12px rgba(52,211,153,0.22)",
        }}
      >
        ⚡
      </div>
    </div>
  );
}

// ── Typing indicator ──────────────────────────────────────────────────────────

const THINKING_PHASES = [
  "Analisando carteira",
  "Consultando APIs",
  "Processando métricas",
  "Elaborando resposta",
];

function AgentThinking() {
  const [phaseIdx, setPhaseIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setPhaseIdx((p) => (p + 1) % THINKING_PHASES.length), 1800);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <style>{`
        @keyframes tm-dot {
          0%, 70%, 100% { transform: translateY(0); opacity: 0.3; }
          35% { transform: translateY(-5px); opacity: 1; }
        }
        .tm-dot { animation: tm-dot 1.3s ease-in-out infinite; }
      `}</style>
      <div className="flex items-start gap-3">
        <AgentAvatar pulsing />
        <div
          className="rounded-2xl rounded-tl-sm border px-4 py-3.5"
          style={{
            background: "var(--paper-deep)",
            borderColor: "rgba(52,211,153,0.18)",
            boxShadow: "0 0 24px rgba(52,211,153,0.06)",
          }}
        >
          <p className="mb-2.5 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--forest)]">
            {THINKING_PHASES[phaseIdx]}
          </p>
          <div className="flex items-center gap-1.5">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="tm-dot h-2 w-2 rounded-full"
                style={{
                  background: "var(--forest)",
                  animationDelay: `${i * 170}ms`,
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TurboMaxPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [clientes, setClientes] = useState<ClienteGestor[]>([]);
  const [clienteSlug, setClienteSlug] = useState("");
  const [userId, setUserId] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const generationRef = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    gestorApi.clientes().then((res) => setClientes(res.items)).catch(() => {});
  }, []);

  useEffect(() => {
    gestorApi.me().then((u) => {
      setUserId(u.id);
      const saved = localStorage.getItem(`turbomax_history_${u.id}`);
      if (saved) {
        try {
          const parsed = JSON.parse(saved) as ChatMessage[];
          if (parsed.length > 0) setMessages(parsed);
        } catch {}
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!userId) return;
    localStorage.setItem(`turbomax_history_${userId}`, JSON.stringify(messages));
  }, [messages, userId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setErro(null);

    const gen = generationRef.current;
    try {
      const res = await gestorApi.chat(newMessages, clienteSlug || undefined);
      if (generationRef.current === gen) {
        setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      }
    } catch (err) {
      if (generationRef.current === gen) {
        const msg = err instanceof Error ? err.message : "Erro ao conectar com o TurboMax.";
        setErro(msg);
      }
    } finally {
      if (generationRef.current === gen) {
        setLoading(false);
      }
    }
  }, [input, loading, messages, clienteSlug]);

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && e.ctrlKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function novaConversa() {
    generationRef.current += 1;
    setMessages([WELCOME]);
    setErro(null);
    setLoading(false);
    if (userId) localStorage.removeItem(`turbomax_history_${userId}`);
    setTimeout(() => textareaRef.current?.focus(), 50);
  }

  return (
    <GestorShell>
      <style>{`
        @keyframes tm-scan {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(400%); }
        }
      `}</style>

      <div className="flex h-screen flex-col overflow-hidden">

        {/* ── Header ── */}
        <div
          className="relative flex-shrink-0 overflow-hidden border-b border-[var(--rule-soft)] px-6 py-4"
          style={{ background: "var(--paper-soft)" }}
        >
          {/* Subtle dot grid */}
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.025]"
            style={{
              backgroundImage: "radial-gradient(circle, var(--forest) 1px, transparent 1px)",
              backgroundSize: "20px 20px",
            }}
          />

          <div className="relative flex items-center justify-between gap-4">
            {/* Brand */}
            <div className="flex items-center gap-4">
              <div className="relative">
                <div
                  className="flex h-11 w-11 items-center justify-center rounded-xl text-xl text-white"
                  style={{
                    background: "var(--forest)",
                    boxShadow: loading
                      ? "0 0 28px rgba(52,211,153,0.55), 0 0 56px rgba(52,211,153,0.2)"
                      : "0 0 16px rgba(52,211,153,0.3)",
                    transition: "box-shadow 0.4s ease",
                  }}
                >
                  ⚡
                </div>
                {loading && (
                  <span className="absolute -inset-1 animate-ping rounded-xl bg-[var(--forest)] opacity-[0.12]" />
                )}
              </div>
              <div>
                <div className="flex items-center gap-2.5">
                  <p className="font-display text-lg font-semibold text-[var(--ink)]">TurboMax</p>
                  <span
                    className="rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest"
                    style={{
                      color: "var(--forest)",
                      borderColor: "rgba(52,211,153,0.3)",
                      background: "rgba(52,211,153,0.07)",
                    }}
                  >
                    AI Agent
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-1.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${loading ? "animate-pulse bg-amber-400" : "bg-emerald-400"}`}
                  />
                  <p className="font-mono text-[10px] text-[var(--muted)]">
                    {loading ? "Processando…" : "Online · especialista em performance digital"}
                  </p>
                </div>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-3">
              <select
                value={clienteSlug}
                onChange={(e) => setClienteSlug(e.target.value)}
                className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-deep)] px-3 py-1.5 text-xs text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none"
              >
                <option value="">Todos os clientes</option>
                {clientes.map((c) => (
                  <option key={c.slug} value={c.slug}>{c.nome}</option>
                ))}
              </select>
              <button
                onClick={novaConversa}
                className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-deep)] px-3 py-1.5 text-xs text-[var(--muted)] transition hover:border-[var(--forest)] hover:text-[var(--ink)]"
              >
                Nova conversa
              </button>
            </div>
          </div>
        </div>

        {/* ── Messages ── */}
        <div
          className="relative flex-1 overflow-hidden"
          style={{
            background: "radial-gradient(ellipse at 50% 38%, rgba(52,211,153,0.045) 0%, transparent 65%), var(--paper)",
          }}
        >
          {/* Turbo Partners watermark — fica fixo enquanto mensagens rolam */}
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center select-none gap-3">
            <span
              className="font-display font-black leading-none"
              style={{
                fontSize: "clamp(72px, 12vw, 140px)",
                color: "var(--forest)",
                opacity: 0.03,
                letterSpacing: "-0.02em",
              }}
            >
              ⚡
            </span>
            <span
              className="font-display font-bold uppercase tracking-[0.28em]"
              style={{
                fontSize: "clamp(11px, 1.4vw, 18px)",
                color: "var(--ink)",
                opacity: 0.06,
              }}
            >
              Turbo Partners
            </span>
          </div>

          {/* Scrollable messages on top */}
          <div className="absolute inset-0 overflow-y-auto px-6 py-6">
          <div className="relative mx-auto max-w-3xl space-y-5">
            {messages.map((msg, i) =>
              msg.role === "user" ? (
                /* User bubble */
                <div key={i} className="flex justify-end">
                  <div
                    className="max-w-[78%] rounded-2xl rounded-tr-sm px-4 py-3 text-white"
                    style={{
                      background: "var(--forest)",
                      boxShadow: "0 2px 12px rgba(52,211,153,0.2)",
                    }}
                  >
                    {renderContent(msg.content)}
                  </div>
                </div>
              ) : (
                /* Assistant bubble */
                <div key={i} className="flex items-start gap-3">
                  <AgentAvatar />
                  <div
                    className="max-w-[84%] rounded-2xl rounded-tl-sm border px-4 py-3.5 text-[var(--ink)]"
                    style={{
                      background: "var(--paper-deep)",
                      borderColor: "var(--rule-soft)",
                    }}
                  >
                    {renderContent(msg.content)}
                  </div>
                </div>
              ),
            )}

            {loading && <AgentThinking />}

            {erro && (
              <div className="rounded-xl border border-red-900/30 bg-red-950/30 px-4 py-3 text-sm text-red-400">
                {erro}
              </div>
            )}

            <div ref={bottomRef} />
          </div>
          </div>
        </div>

        {/* ── Input ── */}
        <div
          className="flex-shrink-0 border-t border-[var(--rule-soft)] px-6 py-4"
          style={{ background: "var(--paper-soft)" }}
        >
          <div className="mx-auto max-w-3xl">
            <div
              className="flex gap-3 rounded-2xl border p-2 transition-all duration-200 focus-within:shadow-[0_0_0_2px_rgba(52,211,153,0.1)]"
              style={{
                background: "var(--paper-deep)",
                borderColor: "var(--rule-soft)",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(52,211,153,0.35)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "var(--rule-soft)")}
            >
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Pergunte qualquer coisa…"
                rows={2}
                disabled={loading}
                className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none disabled:opacity-40"
              />
              <div className="flex flex-col items-end justify-end gap-1">
                <button
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  title="Enviar (Ctrl+Enter)"
                  className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-white transition hover:opacity-90 disabled:opacity-30"
                  style={{ background: "var(--forest)" }}
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
            </div>
            <p className="mt-2 text-center font-mono text-[9px] text-[var(--muted)] opacity-40">
              Ctrl + Enter para enviar
            </p>
          </div>
        </div>

      </div>
    </GestorShell>
  );
}
