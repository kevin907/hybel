"use client";

import type { Message } from "@/types/messaging";
import { cn, formatMessageTime, formatFileSize } from "@/lib/utils";
import { getAttachmentDownloadUrl } from "@/lib/api";
import Avatar from "@/components/ui/Avatar";
import Icon from "@/components/ui/Icon";

interface Props {
  message: Message;
  isOwn: boolean;
}

export default function MessageBubble({ message, isOwn }: Props) {
  // System event
  if (message.message_type === "system_event") {
    return (
      <div className="flex justify-center py-2">
        <p className="text-xs text-gray-400 italic">{message.content}</p>
      </div>
    );
  }

  // Internal comment
  if (message.is_internal) {
    return (
      <div className="flex gap-2.5 px-4 py-2">
        <Avatar
          firstName={message.sender.first_name}
          lastName={message.sender.last_name}
        />
        <div className="max-w-[75%]">
          <div className="mb-0.5 flex items-center gap-2">
            <span className="text-xs font-medium text-gray-700">
              {message.sender.first_name} {message.sender.last_name}
            </span>
            <span className="flex items-center gap-1 text-micro text-amber-600">
              <Icon name="lock" size={10} />
              Intern kommentar
            </span>
            <span className="text-micro text-gray-400">
              {formatMessageTime(message.created_at)}
            </span>
          </div>
          <div className="rounded-lg border border-internal-border bg-internal px-3 py-2">
            <p className="whitespace-pre-wrap text-sm text-gray-800">
              {message.content}
            </p>
            <Attachments message={message} />
          </div>
        </div>
      </div>
    );
  }

  const isPending = message._status === "pending";
  const isFailed = message._status === "failed";

  // Regular message
  return (
    <div
      className={cn(
        "flex gap-2.5 px-4 py-2",
        isOwn ? "flex-row-reverse" : "",
        isPending && "opacity-60"
      )}
    >
      {!isOwn && (
        <Avatar
          firstName={message.sender.first_name}
          lastName={message.sender.last_name}
        />
      )}
      <div className={cn("max-w-[75%]", isOwn ? "items-end" : "")}>
        <div
          className={cn(
            "mb-0.5 flex items-center gap-2",
            isOwn ? "justify-end" : ""
          )}
        >
          {!isOwn && (
            <span className="text-xs font-medium text-gray-700">
              {message.sender.first_name} {message.sender.last_name}
            </span>
          )}
          <span className="text-micro text-gray-400">
            {isPending
              ? "Sender..."
              : isFailed
                ? "Sending feilet"
                : formatMessageTime(message.created_at)}
          </span>
        </div>
        <div
          className={cn(
            "rounded-lg px-3 py-2",
            isFailed
              ? "bg-red-100 border border-red-200 text-red-800"
              : isOwn
                ? "bg-primary text-white"
                : "bg-white border border-gray-100 text-gray-800"
          )}
        >
          <p className="whitespace-pre-wrap text-sm">{message.content}</p>
          <Attachments message={message} isOwn={isOwn} />
        </div>
      </div>
    </div>
  );
}

function Attachments({
  message,
  isOwn = false,
}: {
  message: Message;
  isOwn?: boolean;
}) {
  if (message.attachments.length === 0) return null;

  return (
    <div className="mt-2 space-y-1">
      {message.attachments.map((att) => (
        <a
          key={att.id}
          href={getAttachmentDownloadUrl(att.id)}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "flex items-center gap-2 rounded-md px-2 py-1 text-xs transition-colors",
            isOwn
              ? "bg-white/10 hover:bg-white/20 text-white"
              : "bg-gray-50 hover:bg-gray-100 text-gray-700"
          )}
        >
          <Icon name="paperclip" size={12} />
          <span className="truncate">{att.filename}</span>
          <span className="shrink-0 text-micro opacity-60">
            {formatFileSize(att.file_size)}
          </span>
        </a>
      ))}
    </div>
  );
}
