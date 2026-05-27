"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import GestorShell from "../_shell";
import { gestorApi, type ChatMessage, type ClienteGestor } from "@/lib/api-gestor";

const WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "Olá! Sou o **TurboMax**, seu especialista em performance digital.\n\n" +
    "Posso te ajudar com:\n" +
    "• Análise de ROAS, CPL e métricas de qualquer cliente\n" +
    "• Diagnóstico de campanhas Meta Ads e Google Ads ao vivo\n" +
    "• Comparativos entre clientes da carteira\n" +
    "• Dicas técnicas de otimização\n\n" +
    "Por onde quer começar?",
};

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
      <div key={`table-${elements.length}`} className="overflow-x-auto my-3">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              {cols.map((c, i) => (
                <th key={i} className="border border-[var(--rule-soft)] px-3 py-1.5 text-left bg-[var(--paper-deep)] font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri}>
                {row.split("|").map((c) => c.trim()).filter(Boolean).map((cell, ci) => (
                  <td key={ci} className="border border-[var(--rule-soft)] px-3 py-1.5">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
    tableBuffer = [];
  }

  function flushList() {
    if (listBuffer.length === 0) return;
    elements.push(
      <ul key={`list-${elements.length}`} className="my-1 space-y-0.5">
        {listBuffer}
      </ul>
    );
    listBuffer = [];
  }

  lines.forEach((line, i) => {
    const isListLine = line.startsWith("• ") || line.startsWith("- ");

    if (!isListLine && listBuffer.length > 0) {
      flushList();
    }

    if (line.includes("|")) {
      tableBuffer.push(line);
      return;
    }
    if (tableBuffer.length) flushTable();

    if (!line.trim()) {
      elements.push(<div key={i} className="h-2" />);
      return;
    }
    if (isListLine) {
      const content = line.slice(2);
      listBuffer.push(
        <li key={i} className="text-sm list-disc">
          {renderInline(content)}
        </li>
      );
      return;
    }
    elements.push(<p key={i} className="text-sm leading-relaxed">{renderInline(line)}</p>);
  });
  if (tableBuffer.length) flushTable();
  if (listBuffer.length) flushList();

  return <>{elements}</>;
}

function renderInline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") ? (
          <strong key={i}>{p.slice(2, -2)}</strong>
        ) : (
          p
        )
      )}
    </>
  );
}

export default function TurboMaxPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [clientes, setClientes] = useState<ClienteGestor[]>([]);
  const [clienteSlug, setClienteSlug] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const generationRef = useRef(0);

  useEffect(() => {
    gestorApi.clientes().then((res) => setClientes(res.items)).catch(() => {});
  }, []);

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
    } catch {
      if (generationRef.current === gen) {
        setErro("Erro ao conectar com o TurboMax. Tente novamente.");
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
  }

  return (
    <GestorShell>
      <div className="flex h-screen flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--rule-soft)] px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="text-lg">⚡</span>
            <div>
              <p className="font-display text-base font-medium text-[var(--ink)]">TurboMax</p>
              <p className="text-xs text-[var(--muted)]">Especialista em performance digital</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={clienteSlug}
              onChange={(e) => setClienteSlug(e.target.value)}
              className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none"
            >
              <option value="">Todos os clientes</option>
              {clientes.map((c) => (
                <option key={c.slug} value={c.slug}>{c.nome}</option>
              ))}
            </select>
            <button
              onClick={novaConversa}
              className="text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
            >
              Nova conversa
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={[
                  "flex gap-3",
                  msg.role === "user" ? "justify-end" : "justify-start",
                ].join(" ")}
              >
                {msg.role === "assistant" && (
                  <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[var(--forest)] text-white text-sm">
                    ⚡
                  </div>
                )}
                <div
                  className={[
                    "max-w-[80%] rounded-xl px-4 py-3",
                    msg.role === "user"
                      ? "bg-[var(--forest)] text-white"
                      : "bg-[var(--paper-deep)] text-[var(--ink)]",
                  ].join(" ")}
                >
                  {renderContent(msg.content)}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex gap-3 justify-start">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-[var(--forest)] text-white text-sm">
                  ⚡
                </div>
                <div className="rounded-xl bg-[var(--paper-deep)] px-4 py-3">
                  <p className="text-sm text-[var(--muted)] animate-pulse">
                    TurboMax está consultando...
                  </p>
                </div>
              </div>
            )}

            {erro && (
              <div className="rounded-xl bg-[var(--crimson-soft,#fff5f5)] px-4 py-3 text-sm text-[var(--crimson)]">
                {erro}
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-[var(--rule-soft)] px-6 py-4">
          <div className="mx-auto max-w-3xl flex gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pergunte qualquer coisa... (Ctrl+Enter para enviar)"
              rows={2}
              disabled={loading}
              className="flex-1 resize-none rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--forest)] focus:outline-none disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="rounded-xl bg-[var(--forest)] px-5 py-3 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40"
            >
              Enviar
            </button>
          </div>
        </div>
      </div>
    </GestorShell>
  );
}
