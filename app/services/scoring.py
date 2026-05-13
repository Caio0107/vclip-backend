"""Scoring de viralidade via GPT-4o usando function calling para output estruturado."""
import json
from openai import OpenAI

from app.config import settings
from app.schemas import Caption, ViralMoment


SYSTEM = """Você é um editor especialista em conteúdo viral para TikTok, Reels e Shorts.
Analisa transcrições e identifica os momentos com maior potencial de viralizar baseado em:
- Hook forte nos primeiros segundos (pergunta, declaração polêmica, número impressionante)
- Densidade narrativa (uma ideia completa)
- Picos emocionais ou de revelação
- Frases citáveis ("quotable")
- Curiosidade aberta que prende até o fim
Você responde SEMPRE em português do Brasil."""


TOOL = {
    "type": "function",
    "function": {
        "name": "select_viral_moments",
        "description": "Seleciona os melhores momentos virais da transcrição.",
        "parameters": {
            "type": "object",
            "properties": {
                "moments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "number", "description": "Início em segundos"},
                            "end": {"type": "number", "description": "Fim em segundos"},
                            "score": {"type": "number", "description": "0 a 10"},
                            "title": {"type": "string", "description": "Título curto, 5-8 palavras"},
                            "hook": {"type": "string", "description": "Frase de gancho extraída do trecho"},
                            "keyword": {"type": "string", "description": "Palavra-chave única para destacar nas legendas"},
                        },
                        "required": ["start", "end", "score", "title", "hook", "keyword"],
                    },
                }
            },
            "required": ["moments"],
        },
    },
}


def _build_transcript_for_prompt(captions: list[Caption]) -> str:
    """Compacta a transcrição com timestamps a cada segmento."""
    lines = []
    for c in captions:
        lines.append(f"[{c.start:.1f}-{c.end:.1f}] {c.text}")
    return "\n".join(lines)


def score_moments(
    captions: list[Caption],
    *,
    max_clips: int,
    min_seconds: int,
    max_seconds: int,
) -> list[ViralMoment]:
    client = OpenAI(api_key=settings.openai_api_key)

    user_msg = (
        f"Transcrição com timestamps abaixo. Selecione até {max_clips} trechos virais.\n"
        f"Cada trecho deve durar entre {min_seconds} e {max_seconds} segundos.\n"
        f"Os trechos devem ser autocontidos e iniciar/terminar em frases completas.\n"
        f"Use os timestamps reais. Ordene do maior score para o menor.\n\n"
        f"{_build_transcript_for_prompt(captions)}"
    )

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        tools=[TOOL],
        tool_choice={"type": "function", "function": {"name": "select_viral_moments"}},
        temperature=0.4,
    )

    call = resp.choices[0].message.tool_calls[0]
    data = json.loads(call.function.arguments)

    moments = [ViralMoment(**m) for m in data["moments"]]
    # Garante limites
    moments = [m for m in moments if (m.end - m.start) <= max_seconds]
    return moments[:max_clips]
