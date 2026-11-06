import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

val localSettings = Properties().apply {
    val file = rootProject.file("local.properties")
    if (file.isFile) file.inputStream().use { load(it) }
}
val localApplicationId = localSettings.getProperty("watchchat.applicationId")?.takeIf { it.isNotBlank() }

android {
    namespace = "org.watchchat.app"
    compileSdk = 35
    defaultConfig {
        applicationId = localApplicationId ?: "org.watchchat.app"
        minSdk = 30
        targetSdk = 34
        versionCode = 28
        versionName = "0.13.9"
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (localApplicationId != null && localSettings.getProperty("watchchat.signWithDebugKey") == "true") {
                signingConfig = signingConfigs.getByName("debug")
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    testOptions {
        unitTests.isIncludeAndroidResources = true
        unitTests.all {
            it.systemProperty("robolectric.dependency.repo.url", if (providers.gradleProperty("useRepositoryMirror").orNull == "true") "https://maven.aliyun.com/repository/central" else "https://repo.maven.apache.org/maven2")
        }
    }
}

dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.14.1")
}
