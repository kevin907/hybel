export default function MeldingerPage() {
  return (
    <div className="flex flex-1 items-center justify-center text-gray-400">
      <div className="text-center">
        <svg
          className="mx-auto mb-3 h-12 w-12 text-gray-300"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <p className="text-sm">Velg en samtale fra listen</p>
      </div>
    </div>
  );
}
