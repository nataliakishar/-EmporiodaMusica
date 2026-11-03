import { Chat } from "@/components/chat";
import { ArrowIcon, MusicMark } from "@/components/icons";
import { InstrumentScene } from "@/components/instrument-scene";
import { MotionControl } from "@/components/motion-control";

export default function Home() {
  return <>
    <a className="skip-link" href="#atendimento">Ir para o atendimento</a>
    <header className="site-header mx-auto flex items-center justify-between gap-6">
      <a className="brand" href="#inicio" aria-label="Empório da Música, início"><MusicMark/><span>empório<span>da música<span className="brand-dot">.</span></span></span></a>
      <nav aria-label="Navegação principal" className="flex items-center gap-8"><a className="nav-link" href="#como-funciona">Como funciona</a><a className="nav-chat" href="#atendimento">Vamos conversar<ArrowIcon/></a></nav>
    </header>
    <main id="inicio">
      <section className="hero mx-auto grid items-center" aria-labelledby="hero-title">
        <div className="hero-copy"><p className="eyebrow"><span className="eyebrow-line"/> PARA QUEM SENTE A MÚSICA</p>
          <h1 id="hero-title">O seu próximo<br/><em>som</em> começa<br/>aqui<span className="hero-period">.</span></h1>
          <p className="hero-description">Do primeiro acorde à próxima descoberta.<br/>A gente escuta você e ajuda a encontrar o instrumento que faz sentido.</p>
          <a className="hero-cta" href="#atendimento"><span>Encontre o seu som</span><span className="cta-circle"><ArrowIcon/></span></a>
          <div className="hero-caption"><span aria-hidden="true">↳</span> Você traz a vontade. A conversa dá o tom.</div>
        </div>
        <InstrumentScene/>
        <div className="hero-bottom"><span>INSTRUMENTOS. HISTÓRIAS. POSSIBILIDADES.</span><MotionControl/></div>
      </section>
      <div className="sound-ribbon" aria-hidden="true"><div>{[0, 1].map(index => <span key={index}>MAIS CONVERSA <i>✳</i> MAIS MÚSICA <i>✳</i> MAIS VOCÊ <i>✳</i> </span>)}</div></div>
      <section className="conversation-section mx-auto grid gap-10 lg:grid-cols-[0.8fr_1.2fr]" id="atendimento" aria-labelledby="conversation-title">
        <div className="conversation-intro"><p className="eyebrow">01 / AFINANDO A CONVERSA</p><h2 id="conversation-title">Antes de tocar,<br/>vamos <em>conversar.</em></h2>
          <p>Um modelo em mente? Uma dúvida sobre a loja? Ou só procurando por onde começar? Pode perguntar do seu jeito.</p>
          <div className="topics"><span>Instrumentos</span><span>Preços e estoque</span><span>Políticas da loja</span></div>
          <div className="listening-note"><svg viewBox="0 0 110 45" fill="none" aria-hidden="true"><path d="M3 24h10l4-8 6 17 7-29 8 37 9-30 6 23 5-12 6 5 6-14 5 11h31" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg><p>Respostas com contexto.<br/>Consulta às informações da loja.</p></div>
        </div>
        <Chat/>
      </section>
      <section className="how-section mx-auto" id="como-funciona" aria-labelledby="how-title">
        <div className="how-heading"><p className="eyebrow">02 / CADA COISA NO SEU TEMPO</p><h2 id="how-title">Uma boa conversa.<br/><em>Três pequenos passos.</em></h2></div>
        <div className="how-steps grid md:grid-cols-3">
          <article><span className="step-number">01<span aria-hidden="true">↗</span></span><h3>Solte a primeira nota.</h3><p>Faça sua pergunta em português. Vale falar de um instrumento específico ou contar o que você procura.</p></article>
          <article><span className="step-number">02<span aria-hidden="true">↗</span></span><h3>A gente se apresenta.</h3><p>Antes de seguir, confira nome, telefone e e-mail e confirme o envio dos dados para este atendimento.</p></article>
          <article><span className="step-number">03<span aria-hidden="true">↗</span></span><h3>A conversa ganha ritmo.</h3><p>O assistente consulta catálogo e políticas para responder. Você continua a conversa no seu tempo.</p></article>
        </div>
      </section>
    </main>
    <footer className="site-footer"><div className="footer-inner mx-auto"><a className="brand" href="#inicio" aria-label="Voltar ao início"><MusicMark/><span>empório<span>da música.</span></span></a><p>A sua música começa com você.</p><a href="#atendimento">A próxima conversa é nossa<ArrowIcon/></a></div><div className="footer-small mx-auto"><span>EMPÓRIO DA MÚSICA · LOJA FICTÍCIA</span><span>FEITO PARA OUVIR. PENSADO PARA AJUDAR.</span></div></footer>
  </>;
}
