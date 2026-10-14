class Maude < Formula
  desc "Pinned Maude runtime for RANGER-IoT Tamarin"
  homepage "https://maude.cs.illinois.edu"

  url "https://github.com/maude-lang/Maude/archive/refs/tags/Maude3.5.1.tar.gz"

  version "3.5.1"

  sha256 "3dce4f7b42fae2430a08ab2663303d1be244792bb3cc365c58cdb2f3f7bff170"

  revision 1

  bottle do
    root_url "https://raw.githubusercontent.com/tamarin-prover/binaries/HEAD/dependencies"

    sha256 \
      cellar: :any_skip_relocation,
      x86_64_linux: "3a941ae6e9eaa567827959dcac44129166c87b020d238c742c32467980e99936"
  end

  depends_on "gmp"
  depends_on "ranger/tamarin-pinned/libbuddy"
  depends_on "libsigsegv"
  depends_on "libtecla"
  depends_on "flex"

  def install
    odie("RANGER-IoT reproducibility policy: source build forbidden; expected official bottle")
  end
end
