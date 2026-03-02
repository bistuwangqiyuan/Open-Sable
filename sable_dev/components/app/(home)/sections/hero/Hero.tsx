import { Connector } from "@/components/shared/layout/curvy-rect";
import HeroFlame from "@/components/shared/effects/flame/hero-flame";

import HomeHeroBackground from "./Background/Background";
import { BackgroundOuterPiece } from "./Background/BackgroundOuterPiece";
import HomeHeroBadge from "./Badge/Badge";
import HomeHeroPixi from "./Pixi/Pixi";
import HomeHeroTitle from "./Title/Title";
import HeroInput from "../hero-input/HeroInput";
import HeroScraping from "../hero-scraping/HeroScraping";

export default function HomeHero() {
  return (
    <section className="overflow-x-clip" id="home-hero">
      <div
        className="pt-28 lg:pt-254 lg:-mt-100 pb-115 relative"
        id="hero-content"
      >
        <HomeHeroPixi />
        <HeroFlame />

        <BackgroundOuterPiece />

        <HomeHeroBackground />

        <div className="relative container px-16">
          <HomeHeroBadge />
          <HomeHeroTitle />

          <p className="text-center text-body-large">
            Build anything with AI.
            <br className="lg-max:hidden" />
            Describe it and watch it come to life.
          </p>
        </div>
      </div>

      <div className="container lg:contents !p-16 relative -mt-90">
        <div className="absolute top-0 left-[calc(50%-50vw)] w-screen h-1 bg-border-faint lg:hidden" />
        <div className="absolute bottom-0 left-[calc(50%-50vw)] w-screen h-1 bg-border-faint lg:hidden" />

        <Connector className="-top-10 -left-[10.5px] lg:hidden" />
        <Connector className="-top-10 -right-[10.5px] lg:hidden" />
        <Connector className="-bottom-10 -left-[10.5px] lg:hidden" />
        <Connector className="-bottom-10 -right-[10.5px] lg:hidden" />

        <HeroInput />
      </div>

      <HeroScraping />
    </section>
  );
}
