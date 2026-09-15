type WeatherCardsProps = {
  notes: string[];
};

export function WeatherCards({ notes }: WeatherCardsProps) {
  if (!notes.length) {
    return (
      <section className="rounded-2xl border border-tide/10 bg-foam/90 p-5">
        <h2 className="font-display text-xl text-tide">Thời tiết</h2>
        <p className="mt-2 text-sm text-ink/60">Không có ghi chú thời tiết cho kế hoạch này.</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-tide/10 bg-foam/90 p-5">
      <h2 className="font-display text-xl text-tide">Thời tiết</h2>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {notes.map((note) => (
          <article
            key={note}
            className="rounded-xl border border-lagoon/15 bg-mist/60 px-4 py-3 text-sm text-ink/80"
          >
            {note}
          </article>
        ))}
      </div>
    </section>
  );
}
