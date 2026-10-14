class Libbuddy < Formula
  desc "Pinned BuDDy runtime for RANGER-IoT Tamarin"
  homepage "https://sourceforge.net/projects/buddy/"

  url "https://downloads.sourceforge.net/project/buddy/buddy/BuDDy%202.4/buddy-2.4.tar.gz"

  version "2.4"

  sha256 "d3df80a6a669d9ae408cb46012ff17bd33d855529d20f3a7e563d0d913358836"

  bottle do
    root_url "https://raw.githubusercontent.com/tamarin-prover/binaries/HEAD/dependencies"

    rebuild 3

    sha256 \
      cellar: :any_skip_relocation,
      x86_64_linux: "0807d5706dc37213dbc466b06819fc1b93d710c3543b92eec3c07e7c4fc317d5"
  end

  def install
    odie("RANGER-IoT reproducibility policy: source build forbidden; expected official bottle")
  end
end
