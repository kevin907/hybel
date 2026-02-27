"use client";

import { useState, useRef, useCallback, useEffect, type KeyboardEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api";
import { useMessagingStore } from "@/stores/messaging";
import { getWebSocketManager } from "@/lib/websocket";
import { cn } from "@/lib/utils";
import { queryKeys } from "@/lib/queryKeys";
import Icon from "@/components/ui/Icon";

interface Props {
  conversationId: string;
  userSide?: "tenant_side" | "landlord_side";
}

export default function ComposeBox({ conversationId, userSide }: Props) {
  const [content, setContent] = useState("");
  const [isInternal, setIsInternal] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const addMessage = useMessagingStore((s) => s.addMessage);
  const isLandlordSide = userSide === "landlord_side";

  // ── Typing indicator events ──
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isTypingRef = useRef(false);

  const emitTypingStart = useCallback(() => {
    const ws = getWebSocketManager();
    if (!isTypingRef.current) {
      isTypingRef.current = true;
      ws.sendTypingStart(conversationId);
    }
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    typingTimeoutRef.current = setTimeout(() => {
      isTypingRef.current = false;
      ws.sendTypingStop(conversationId);
    }, 2000);
  }, [conversationId]);

  const emitTypingStop = useCallback(() => {
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
      typingTimeoutRef.current = null;
    }
    if (isTypingRef.current) {
      isTypingRef.current = false;
      getWebSocketManager().sendTypingStop(conversationId);
    }
  }, [conversationId]);

  useEffect(() => {
    return () => emitTypingStop();
  }, [emitTypingStop]);

  const sendMutation = useMutation({
    mutationFn: async () => {
      const msg = await api.sendMessage(conversationId, {
        content: content.trim(),
        is_internal: isInternal,
      });

      // Upload attachments
      for (const file of files) {
        await api.uploadAttachment(conversationId, msg.id, file);
      }

      return msg;
    },
    onSuccess: (msg) => {
      addMessage(msg);
      setContent("");
      setFiles([]);
      setIsInternal(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.conversations });
      queryClient.invalidateQueries({
        queryKey: queryKeys.messages(conversationId),
      });
    },
  });

  const handleSubmit = useCallback(() => {
    if (!content.trim() || sendMutation.isPending) return;
    emitTypingStop();
    sendMutation.mutate();
  }, [content, sendMutation, emitTypingStop]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles([...files, ...Array.from(e.target.files)]);
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div
      className={cn(
        "border-t px-4 py-3",
        isInternal ? "border-internal-border bg-internal" : "border-gray-200"
      )}
    >
      {/* Internal toggle */}
      {isLandlordSide && (
        <div className="mb-2 flex items-center gap-2">
          <button
            onClick={() => setIsInternal(!isInternal)}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              isInternal
                ? "bg-amber-200 text-amber-800"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            )}
          >
            {isInternal ? "Intern kommentar" : "Melding"}
          </button>
          {isInternal && (
            <span className="text-[10px] text-amber-600">
              Kun synlig for utleiersiden
            </span>
          )}
        </div>
      )}

      {/* File previews */}
      {files.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {files.map((file, i) => (
            <div
              key={i}
              className="flex items-center gap-1.5 rounded-md bg-gray-100 px-2 py-1 text-xs text-gray-700"
            >
              <span className="max-w-[120px] truncate">{file.name}</span>
              <button
                onClick={() => removeFile(i)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2">
        <button
          onClick={handleFileSelect}
          className="mb-1 shrink-0 text-gray-400 hover:text-gray-600"
        >
          <Icon name="paperclip" size={18} />
        </button>

        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => {
            setContent(e.target.value);
            if (e.target.value) emitTypingStart();
            else emitTypingStop();
          }}
          onKeyDown={handleKeyDown}
          placeholder={isInternal ? "Skriv intern kommentar..." : "Skriv en melding..."}
          rows={1}
          className={cn(
            "flex-1 resize-none rounded-lg border px-3 py-2 text-sm outline-none transition-colors",
            "max-h-32",
            isInternal
              ? "border-amber-300 bg-white focus:border-amber-400 focus:ring-1 focus:ring-amber-400"
              : "border-gray-200 focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
          )}
          style={{
            height: "auto",
            minHeight: "38px",
          }}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = "auto";
            target.style.height = `${Math.min(target.scrollHeight, 128)}px`;
          }}
        />

        <button
          onClick={handleSubmit}
          disabled={!content.trim() || sendMutation.isPending}
          className={cn(
            "mb-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors",
            content.trim() && !sendMutation.isPending
              ? "bg-primary text-white hover:bg-primary-dark"
              : "bg-gray-200 text-gray-400"
          )}
        >
          {sendMutation.isPending ? (
            <Icon name="spinner" className="h-4 w-4 animate-spin" />
          ) : (
            <Icon name="send" />
          )}
        </button>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  );
}
