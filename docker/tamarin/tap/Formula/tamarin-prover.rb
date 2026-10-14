class TamarinProver < Formula
  desc "Pinned Tamarin Prover for RANGER-IoT"
  homepage "https://tamarin-prover.com/"

  url "https://github.com/tamarin-prover/tamarin-prover/archive/refs/tags/1.12.0.tar.gz"

  version "1.12.0"

  sha256 "35f0262e770db3632fcb297deb6ecc2d7c724c693fecfe97892e8224fa161956"

  bottle do
    root_url "https://github.com/tamarin-prover/tamarin-prover/releases/download/1.12.0"

    sha256 \
      cellar: :any_skip_relocation,
      x86_64_linux: "936631c692ce9fd4c797400eff32e47d6d09e371ca251250cceac15b93f71d99"
  end

  depends_on "graphviz"
  depends_on "ranger/tamarin-pinned/maude"

  def install
    odie("RANGER-IoT reproducibility policy: source build forbidden; expected official 1.12.0 bottle")
  end

  test do
    system "#{bin}/tamarin-prover", "test"
  end
end
